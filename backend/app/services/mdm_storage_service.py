"""SQLite persistence and dataset merging service for Polar-EMS MDM."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..db import get_conn, tx
from ..schemas.mdm_models import DatasetMetadata, MdmStatus

MDM_SCHEMA = """
CREATE TABLE IF NOT EXISTS mdm_datasets (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    upload_timestamp REAL NOT NULL,
    rows_detected INTEGER NOT NULL,
    rows_accepted INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL,
    columns_detected TEXT NOT NULL,
    columns_mapped TEXT NOT NULL,
    columns_ignored TEXT NOT NULL,
    duplicates_removed INTEGER NOT NULL,
    missing_values_handled INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT,
    stations TEXT NOT NULL,
    file_size_bytes INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mdm_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    station TEXT NOT NULL,
    ts REAL NOT NULL,
    timestamp TEXT NOT NULL,
    energy_consumption REAL,
    temperature REAL,
    solar_generation REAL,
    wind_speed REAL,
    wind_generation REAL,
    battery_level REAL,
    equipment_load REAL,
    equipment_id TEXT,
    equipment_status TEXT,
    equipment_runtime REAL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_mdm_station_ts ON mdm_records(station, ts);
CREATE INDEX IF NOT EXISTS idx_mdm_ts ON mdm_records(ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_mdm_unique_record ON mdm_records(station, ts);
"""


def init_mdm_schema() -> None:
    """Ensure MDM tables exist in SQLite."""
    conn = get_conn()
    conn.executescript(MDM_SCHEMA)
    conn.commit()


def save_cleaned_dataset(
    filename: str,
    cleaned_data: Dict[str, Any],
    file_size_bytes: int = 0
) -> Dict[str, Any]:
    """
    Saves a cleaned dataset and merges records into mdm_records.
    Detects and ignores cross-upload duplicates (deduplication on station + ts).
    """
    init_mdm_schema()
    dataset_id = str(uuid.uuid4())[:8]
    stats = cleaned_data["stats"]
    records = cleaned_data["records"]

    conn = get_conn()
    # Check existing (station, ts) records in database to count cross-dataset duplicates
    existing_keys = set()
    rows = conn.execute("SELECT station, ts FROM mdm_records").fetchall()
    for r in rows:
        existing_keys.add((r["station"], round(float(r["ts"]), 1)))

    new_records_to_insert = []
    cross_duplicates_count = 0

    for rec in records:
        key = (rec["station"], round(float(rec["ts"]), 1))
        if key in existing_keys:
            cross_duplicates_count += 1
            continue
        existing_keys.add(key)
        new_records_to_insert.append(rec)

    total_duplicates_removed = stats["duplicates_removed"] + cross_duplicates_count

    # Insert dataset metadata
    with tx() as c:
        c.execute(
            """
            INSERT INTO mdm_datasets (
                id, filename, upload_timestamp, rows_detected, rows_accepted,
                rows_rejected, columns_detected, columns_mapped, columns_ignored,
                duplicates_removed, missing_values_handled, start_date, end_date,
                stations, file_size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                filename,
                time.time(),
                stats["rows_detected"],
                len(new_records_to_insert),
                stats["rows_rejected"],
                json.dumps(stats["columns_detected"]),
                json.dumps(stats["columns_mapped"]),
                json.dumps(stats["columns_ignored"]),
                total_duplicates_removed,
                stats["missing_values_handled"],
                stats.get("start_date"),
                stats.get("end_date"),
                json.dumps(stats.get("stations", [])),
                file_size_bytes
            )
        )

        # Batch insert new records
        if new_records_to_insert:
            c.executemany(
                """
                INSERT OR IGNORE INTO mdm_records (
                    dataset_id, station, ts, timestamp, energy_consumption,
                    temperature, solar_generation, wind_speed, wind_generation,
                    battery_level, equipment_load, equipment_id, equipment_status,
                    equipment_runtime, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        dataset_id,
                        r["station"],
                        r["ts"],
                        r["timestamp"],
                        r.get("energy_consumption"),
                        r.get("temperature"),
                        r.get("solar_generation"),
                        r.get("wind_speed"),
                        r.get("wind_generation"),
                        r.get("battery_level"),
                        r.get("equipment_load"),
                        r.get("equipment_id", f"{r['station']}-Plant"),
                        r.get("equipment_status", "NORMAL"),
                        r.get("equipment_runtime"),
                        json.dumps(r)
                    )
                    for r in new_records_to_insert
                ]
            )

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "rows_detected": stats["rows_detected"],
        "rows_accepted": len(new_records_to_insert),
        "rows_rejected": stats["rows_rejected"],
        "columns_detected": stats["columns_detected"],
        "columns_mapped": stats["columns_mapped"],
        "columns_ignored": stats["columns_ignored"],
        "duplicates_removed": total_duplicates_removed,
        "missing_values_handled": stats["missing_values_handled"],
        "start_date": stats.get("start_date"),
        "end_date": stats.get("end_date"),
        "stations_detected": stats.get("stations", []),
        "merge_status": f"Merged {len(new_records_to_insert)} records into unified historical repository (skipped {cross_duplicates_count} duplicate timestamps)."
    }


def get_mdm_status() -> MdmStatus:
    """Returns overall status of MDM dataset."""
    init_mdm_schema()
    conn = get_conn()

    count_row = conn.execute("SELECT COUNT(*) as c FROM mdm_records").fetchone()
    total_records = count_row["c"] if count_row else 0

    if total_records == 0:
        return MdmStatus(
            has_data=False,
            records_count=0,
            stations_count=0,
            stations=[],
            date_range_start=None,
            date_range_end=None,
            datasets_count=0,
            available_variables=[],
            datasets=[]
        )

    stations_rows = conn.execute("SELECT DISTINCT station FROM mdm_records ORDER BY station").fetchall()
    stations = [r["station"] for r in stations_rows if r["station"]]

    range_row = conn.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM mdm_records").fetchone()
    date_start = range_row["min_ts"] if range_row else None
    date_end = range_row["max_ts"] if range_row else None

    # Detect populated variables
    vars_detected = []
    for var in ["energy_consumption", "temperature", "solar_generation", "wind_speed", "battery_level", "equipment_load"]:
        chk = conn.execute(f"SELECT COUNT(*) as c FROM mdm_records WHERE {var} IS NOT NULL").fetchone()
        if chk and chk["c"] > 0:
            vars_detected.append(var)

    # Fetch datasets list
    ds_rows = conn.execute("SELECT * FROM mdm_datasets ORDER BY upload_timestamp DESC").fetchall()
    datasets: List[DatasetMetadata] = []
    for ds in ds_rows:
        datasets.append(
            DatasetMetadata(
                id=ds["id"],
                filename=ds["filename"],
                upload_timestamp=ds["upload_timestamp"],
                rows_detected=ds["rows_detected"],
                rows_accepted=ds["rows_accepted"],
                rows_rejected=ds["rows_rejected"],
                columns_detected=json.loads(ds["columns_detected"]),
                columns_mapped=json.loads(ds["columns_mapped"]),
                columns_ignored=json.loads(ds["columns_ignored"]),
                duplicates_removed=ds["duplicates_removed"],
                missing_values_handled=ds["missing_values_handled"],
                start_date=ds["start_date"],
                end_date=ds["end_date"],
                stations=json.loads(ds["stations"]),
                file_size_bytes=ds["file_size_bytes"]
            )
        )

    return MdmStatus(
        has_data=True,
        records_count=total_records,
        stations_count=len(stations),
        stations=stations,
        date_range_start=date_start,
        date_range_end=date_end,
        datasets_count=len(datasets),
        available_variables=vars_detected,
        datasets=datasets
    )


def query_mdm_records(
    station: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Queries cleaned MDM records with optional filters."""
    init_mdm_schema()
    conn = get_conn()

    clauses = []
    params = []

    if station and station.lower() != "all" and station.lower() != "all stations":
        clauses.append("station = ?")
        params.append(station)

    if start_date:
        clauses.append("timestamp >= ?")
        params.append(start_date)

    if end_date:
        # Include full day if only date is passed
        end_val = f"{end_date} 23:59:59" if len(end_date) == 10 else end_date
        clauses.append("timestamp <= ?")
        params.append(end_val)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    sql = f"SELECT * FROM mdm_records {where_sql} ORDER BY ts ASC {limit_sql}"
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def clear_mdm_data() -> None:
    """Clears all MDM records and datasets for clean reset."""
    init_mdm_schema()
    with tx() as c:
        c.execute("DELETE FROM mdm_records")
        c.execute("DELETE FROM mdm_datasets")
