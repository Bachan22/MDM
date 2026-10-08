"""Data cleaning, validation, type conversion and normalization service for Polar-EMS MDM.
Supports both CSV (.csv) and Excel (.xlsx, .xls) files.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .schema_mapping_service import map_columns


def parse_timestamp(val: Any) -> Optional[Tuple[float, str]]:
    """
    Parses various timestamp representations (ISO string, standard formats, pandas Timestamp, Excel date numbers).
    Returns (epoch_seconds, iso_utc_string) or None if invalid.
    """
    if val is None:
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        if pd.isna(val):
            return None
        dt = val.to_pydatetime() if hasattr(val, "to_pydatetime") else val
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S")

    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "null", "none", ""):
        return None

    # Check numeric epoch timestamp or Excel serial date
    try:
        num = float(s)
        if num > 1e11:  # ms epoch
            dt = datetime.fromtimestamp(num / 1000.0, tz=timezone.utc)
            return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S")
        elif num > 1e8:  # sec epoch
            dt = datetime.fromtimestamp(num, tz=timezone.utc)
            return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S")
        elif 30000 <= num <= 100000:
            # Valid Excel serial date range (1982 to 2173)
            dt = pd.to_datetime(num, unit="D", origin="1899-12-30").to_pydatetime()
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return None
    except Exception:
        pass

    # Clean string
    s_clean = s.replace("T", " ").replace("Z", "").strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s_clean, fmt).replace(tzinfo=timezone.utc)
            return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    return None


def parse_numeric(val: Any) -> Optional[float]:
    """Extracts clean float from string like '182.4 kW', ' -21.5°C', '85%'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if str(val) == "nan" or pd.isna(val):
            return None
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in ("nan", "null", "none", "n/a", "--"):
        return None
    match = re.search(r"[-+]?\d*\.?\d+", s)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def clean_raw_rows(
    headers: List[str],
    rows: List[List[Any]],
    default_station: str = "Station-A"
) -> Dict[str, Any]:
    """Cleans a 2D matrix of header and row data."""
    # Filter out empty headers
    headers = [str(h).strip() for h in headers if str(h).strip()]
    if not headers:
        return {
            "success": False,
            "error": "No valid column headers found.",
            "records": [],
            "stats": {}
        }

    mapped_cols, ignored_cols, classification = map_columns(headers)

    if "timestamp" not in mapped_cols.values():
        return {
            "success": False,
            "error": "No valid timestamp or date column detected in headers.",
            "records": [],
            "stats": {
                "headers": headers,
                "mapped_columns": mapped_cols,
                "ignored_columns": ignored_cols
            }
        }

    idx_to_canonical: Dict[int, str] = {}
    for idx, h in enumerate(headers):
        if h in mapped_cols:
            idx_to_canonical[idx] = mapped_cols[h]

    raw_rows_count = 0
    accepted_records: List[Dict[str, Any]] = []
    rejected_rows_count = 0
    missing_values_handled_count = 0
    seen_signatures = set()
    duplicates_removed_count = 0

    numeric_fields = [
        "energy_consumption", "temperature", "solar_generation",
        "wind_speed", "wind_generation", "battery_level",
        "equipment_load", "equipment_runtime"
    ]

    for row in rows:
        if not row or all(pd.isna(c) or str(c).strip() == "" for c in row):
            continue
        raw_rows_count += 1

        record: Dict[str, Any] = {}
        for idx, val in enumerate(row):
            if idx in idx_to_canonical:
                canonical_name = idx_to_canonical[idx]
                record[canonical_name] = str(val).strip() if isinstance(val, str) else val

        ts_val = record.get("timestamp")
        parsed_ts = parse_timestamp(ts_val)
        if not parsed_ts:
            rejected_rows_count += 1
            continue

        epoch_ts, iso_ts = parsed_ts
        record["ts"] = epoch_ts
        record["timestamp"] = iso_ts

        station_val = str(record.get("station") or "").strip()
        if not station_val or station_val.lower() in ("nan", "none", "null"):
            station_val = default_station
            missing_values_handled_count += 1
        record["station"] = station_val

        has_any_metric = False
        for num_field in numeric_fields:
            if num_field in record:
                cleaned_num = parse_numeric(record[num_field])
                if cleaned_num is not None:
                    record[num_field] = cleaned_num
                    has_any_metric = True
                else:
                    record[num_field] = None
                    missing_values_handled_count += 1

        if not has_any_metric and len(mapped_cols) > 2:
            rejected_rows_count += 1
            continue

        if "equipment_id" in record:
            eq_str = str(record["equipment_id"]).strip()
            record["equipment_id"] = eq_str if eq_str and eq_str.lower() != "nan" else f"{station_val}-Plant"
        else:
            record["equipment_id"] = f"{station_val}-Plant"

        if "equipment_status" in record:
            st_str = str(record["equipment_status"]).strip()
            record["equipment_status"] = st_str if st_str and st_str.lower() != "nan" else "NORMAL"
        else:
            record["equipment_status"] = "NORMAL"

        sig = (
            record["station"],
            round(record["ts"], 1),
            record.get("energy_consumption"),
            record.get("equipment_load"),
            record.get("temperature")
        )
        if sig in seen_signatures:
            duplicates_removed_count += 1
            continue
        seen_signatures.add(sig)

        accepted_records.append(record)

    accepted_records.sort(key=lambda r: r["ts"])

    # Interpolate / fill minor isolated gaps
    stations = sorted(list({r["station"] for r in accepted_records}))
    for st in stations:
        st_records = [r for r in accepted_records if r["station"] == st]
        for num_field in numeric_fields:
            values = [r.get(num_field) for r in st_records if r.get(num_field) is not None]
            if not values:
                continue
            last_val = values[0]
            for r in st_records:
                if r.get(num_field) is None:
                    r[num_field] = last_val
                    missing_values_handled_count += 1
                else:
                    last_val = r[num_field]

    start_date = accepted_records[0]["timestamp"] if accepted_records else None
    end_date = accepted_records[-1]["timestamp"] if accepted_records else None

    return {
        "success": True,
        "records": accepted_records,
        "stats": {
            "rows_detected": raw_rows_count,
            "rows_accepted": len(accepted_records),
            "rows_rejected": rejected_rows_count,
            "columns_detected": headers,
            "columns_mapped": mapped_cols,
            "columns_ignored": ignored_cols,
            "classification": classification,
            "duplicates_removed": duplicates_removed_count,
            "missing_values_handled": missing_values_handled_count,
            "start_date": start_date,
            "end_date": end_date,
            "stations": stations
        }
    }


def clean_csv_content(csv_text: str, default_station: str = "Station-A") -> Dict[str, Any]:
    """Cleans a CSV string."""
    f = io.StringIO(csv_text.strip())
    sample = csv_text[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    f.seek(0)
    reader = csv.reader(f, delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        return {
            "success": False,
            "error": "Empty CSV file provided.",
            "records": [],
            "stats": {}
        }

    rows = list(reader)
    return clean_raw_rows(headers, rows, default_station)


def find_header_row_and_data(df_raw: pd.DataFrame) -> Tuple[List[str], List[List[Any]]]:
    """
    Scans the top 10 rows of a raw pandas DataFrame to find the true header row
    containing a recognizable timestamp/date column.
    """
    if df_raw.empty:
        return [], []
    headers = [str(c).strip() for c in df_raw.columns]
    m_cols, _, _ = map_columns(headers)
    if "timestamp" in m_cols.values():
        return headers, df_raw.values.tolist()

    for r_idx in range(min(10, len(df_raw))):
        row_vals = [str(v).strip() for v in df_raw.iloc[r_idx].values if pd.notna(v)]
        m_cols, _, _ = map_columns(row_vals)
        if "timestamp" in m_cols.values():
            headers = [str(v).strip() for v in df_raw.iloc[r_idx].values]
            data_rows = df_raw.iloc[r_idx + 1:].values.tolist()
            return headers, data_rows

    return headers, df_raw.values.tolist()


def clean_dataset_bytes(
    file_bytes: bytes,
    filename: str,
    sheet_name: Optional[str] = None,
    default_station: str = "Station-A"
) -> Dict[str, Any]:
    """
    Unified file processor accepting both CSV (.csv) and Excel (.xlsx, .xls) binary content.
    Scans, validates, cleans and merges telemetry records from all valid worksheets.
    """
    fn_lower = filename.lower()
    if fn_lower.endswith(".csv"):
        try:
            csv_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                csv_text = file_bytes.decode("latin-1")
            except Exception:
                return {"success": False, "error": "Could not decode CSV text file."}
        return clean_csv_content(csv_text, default_station)

    if fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls"):
        engine = "openpyxl" if fn_lower.endswith(".xlsx") else "xlrd"
        try:
            excel_file = pd.ExcelFile(io.BytesIO(file_bytes), engine=engine)
            sheet_names = excel_file.sheet_names
        except ImportError as ie:
            return {
                "success": False,
                "error": "Excel processing is currently unavailable on the server. Please contact the system administrator."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Invalid Excel workbook or file is corrupted: {str(e)}"
            }

        target_sheets = [sheet_name] if (sheet_name and sheet_name in sheet_names) else sheet_names
        all_sheet_records: List[Dict[str, Any]] = []
        combined_stats: Dict[str, Any] = {
            "rows_detected": 0,
            "rows_accepted": 0,
            "rows_rejected": 0,
            "columns_detected": [],
            "columns_mapped": {},
            "columns_ignored": [],
            "duplicates_removed": 0,
            "missing_values_handled": 0,
            "stations": set(),
            "excel_sheets": sheet_names,
            "processed_sheets": []
        }

        seen_global_signatures = set()

        for s_name in target_sheets:
            try:
                df_raw = excel_file.parse(sheet_name=s_name)
                if df_raw.empty:
                    continue
                headers, data_rows = find_header_row_and_data(df_raw)
                res = clean_raw_rows(headers, data_rows, default_station)
                if res.get("success") and res.get("records"):
                    combined_stats["processed_sheets"].append(s_name)
                    st = res["stats"]
                    combined_stats["rows_detected"] += st["rows_detected"]
                    combined_stats["rows_rejected"] += st["rows_rejected"]
                    combined_stats["missing_values_handled"] += st["missing_values_handled"]
                    combined_stats["duplicates_removed"] += st["duplicates_removed"]
                    if not combined_stats["columns_detected"]:
                        combined_stats["columns_detected"] = st.get("columns_detected", [])
                        combined_stats["columns_mapped"] = st.get("columns_mapped", {})
                        combined_stats["columns_ignored"] = st.get("columns_ignored", [])

                    for rec in res["records"]:
                        sig = (rec["station"], round(rec["ts"], 1))
                        if sig in seen_global_signatures:
                            combined_stats["duplicates_removed"] += 1
                            continue
                        seen_global_signatures.add(sig)
                        all_sheet_records.append(rec)
                        combined_stats["stations"].add(rec["station"])
            except Exception as e:
                continue

        if not all_sheet_records:
            return {
                "success": False,
                "error": "No valid telemetry data or required timestamp column found in Excel workbook."
            }

        all_sheet_records.sort(key=lambda r: r["ts"])
        combined_stats["rows_accepted"] = len(all_sheet_records)
        combined_stats["start_date"] = all_sheet_records[0]["timestamp"]
        combined_stats["end_date"] = all_sheet_records[-1]["timestamp"]
        combined_stats["stations"] = sorted(list(combined_stats["stations"]))

        combined_stats["selected_sheet"] = combined_stats["processed_sheets"][0] if combined_stats["processed_sheets"] else None
        return {
            "success": True,
            "records": all_sheet_records,
            "stats": combined_stats
        }

    return {
        "success": False,
        "error": f"Unsupported file extension in '{filename}'. Supported formats: .csv, .xlsx, .xls"
    }
