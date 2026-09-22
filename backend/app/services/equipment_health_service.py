"""Equipment health & operational anomaly detection service for Polar-EMS MDM."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..schemas.mdm_models import EquipmentHealthAnalytics, EquipmentHealthRecord
from .mdm_storage_service import query_mdm_records


def calculate_equipment_health_analytics(
    station: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> EquipmentHealthAnalytics:
    """Performs statistical anomaly detection and equipment health evaluation."""
    records = query_mdm_records(station=station, start_date=start_date, end_date=end_date)

    if not records:
        return EquipmentHealthAnalytics(
            has_data=False,
            records_analyzed=0,
            anomalies_detected=0,
            high_risk_signals_count=0,
            overall_risk_level="LOW",
            methodology_note="No records available.",
            missing_fields_notice=["No records found matching filters or no dataset uploaded."]
        )

    # Check available equipment variables
    has_load = any(r.get("equipment_load") is not None for r in records)
    has_energy = any(r.get("energy_consumption") is not None for r in records)
    has_temp = any(r.get("temperature") is not None for r in records)
    has_status = any(r.get("equipment_status") not in (None, "NORMAL") for r in records)

    missing_notices = []
    if not has_load:
        missing_notices.append("Equipment load column unavailable; assessing health from power consumption & temperature.")
    if not has_temp:
        missing_notices.append("Operating temperature column unavailable.")

    # Calculate baseline metrics for anomaly detection (load or energy)
    primary_metric_name = "equipment_load" if has_load else "energy_consumption"
    metric_vals = [float(r[primary_metric_name]) for r in records if r.get(primary_metric_name) is not None]

    if not metric_vals:
        return EquipmentHealthAnalytics(
            has_data=False,
            records_analyzed=len(records),
            anomalies_detected=0,
            high_risk_signals_count=0,
            overall_risk_level="LOW",
            methodology_note="No equipment load or energy metrics detected.",
            missing_fields_notice=["No equipment-related metrics available in uploaded dataset."]
        )

    mean_val = sum(metric_vals) / len(metric_vals)
    variance = sum((x - mean_val) ** 2 for x in metric_vals) / max(1, len(metric_vals) - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 1.0

    # Temperature stats
    temp_vals = [float(r["temperature"]) for r in records if r.get("temperature") is not None]
    temp_mean = (sum(temp_vals) / len(temp_vals)) if temp_vals else -15.0
    temp_std = math.sqrt(sum((t - temp_mean) ** 2 for t in temp_vals) / max(1, len(temp_vals) - 1)) if len(temp_vals) > 1 else 5.0

    anomalies: List[Dict[str, Any]] = []
    equipment_stats: Dict[str, Dict[str, Any]] = {}

    for r in records:
        eq_id = r.get("equipment_id") or f"{r['station']}-Plant"
        if eq_id not in equipment_stats:
            equipment_stats[eq_id] = {
                "station": r["station"],
                "equipment_id": eq_id,
                "anomalies_count": 0,
                "high_load_count": 0,
                "high_temp_count": 0,
                "fault_count": 0,
                "last_observed": r["timestamp"],
                "last_load": r.get(primary_metric_name),
                "last_temp": r.get("temperature"),
                "loads": [],
                "temps": []
            }

        eq = equipment_stats[eq_id]
        eq["last_observed"] = r["timestamp"]

        val = float(r[primary_metric_name]) if r.get(primary_metric_name) is not None else None
        temp = float(r["temperature"]) if r.get("temperature") is not None else None

        if val is not None:
            eq["loads"].append(val)
            eq["last_load"] = val
        if temp is not None:
            eq["temps"].append(temp)
            eq["last_temp"] = temp

        is_anomaly = False
        signal_reasons = []

        # Statistical check: z-score > 2.2
        if val is not None and std_dev > 0:
            z_score = (val - mean_val) / std_dev
            if z_score > 2.2:
                is_anomaly = True
                eq["high_load_count"] += 1
                signal_reasons.append(f"High load surge ({round(val, 1)} kW, z={round(z_score, 1)})")

        # Thermal stress check (temp > mean + 2.5*std)
        if temp is not None and temp_std > 0:
            temp_z = (temp - temp_mean) / temp_std
            if temp_z > 2.5:
                is_anomaly = True
                eq["high_temp_count"] += 1
                signal_reasons.append(f"Abnormal operating thermal excursion ({round(temp, 1)}°C)")

        # Status check
        if r.get("equipment_status") not in (None, "NORMAL", "OK", "0", ""):
            is_anomaly = True
            eq["fault_count"] += 1
            signal_reasons.append(f"Status alert: {r.get('equipment_status')}")

        if is_anomaly:
            eq["anomalies_count"] += 1
            anomalies.append({
                "timestamp": r["timestamp"],
                "equipment_id": eq_id,
                "station": r["station"],
                "metric_value": round(val, 2) if val is not None else None,
                "temperature": round(temp, 1) if temp is not None else None,
                "reason": ", ".join(signal_reasons)
            })

    # Build equipment health records
    equipment_records: List[EquipmentHealthRecord] = []
    high_risk_count = 0

    for eq_id, stats in equipment_stats.items():
        anom_cnt = stats["anomalies_count"]
        # Determine risk level from anomaly frequency
        tot_obs = max(1, len(stats["loads"]))
        anomaly_rate = anom_cnt / tot_obs

        if stats["fault_count"] > 0 or anomaly_rate > 0.08:
            risk = "HIGH"
            high_risk_count += 1
        elif anomaly_rate > 0.03 or anom_cnt > 3:
            risk = "MODERATE"
        else:
            risk = "LOW"

        # Determine main signal
        signals = []
        if stats["fault_count"] > 0:
            signals.append("Reported equipment fault")
        if stats["high_temp_count"] > stats["high_load_count"]:
            signals.append("Thermal excursion / high operating temperature")
        elif stats["high_load_count"] > 0:
            signals.append("Sustained peak load excursions")
        else:
            signals.append("Operating within nominal baseline parameters")

        avg_load = (sum(stats["loads"]) / len(stats["loads"])) if stats["loads"] else None
        avg_temp = (sum(stats["temps"]) / len(stats["temps"])) if stats["temps"] else None

        equipment_records.append(
            EquipmentHealthRecord(
                equipment_id=eq_id,
                station=stats["station"],
                risk_level=risk,
                main_signal=signals[0],
                anomaly_count=anom_cnt,
                last_observed=stats["last_observed"],
                operating_temp_c=round(avg_temp, 1) if avg_temp is not None else None,
                current_load_kw=round(stats["last_load"], 2) if stats["last_load"] is not None else None
            )
        )

    # Sort equipment records by anomaly count descending
    equipment_records.sort(key=lambda r: r.anomaly_count, reverse=True)

    # Overall network equipment risk
    if high_risk_count > 0:
        overall_risk = "HIGH"
    elif len(anomalies) > 5:
        overall_risk = "MODERATE"
    else:
        overall_risk = "LOW"

    # Charts downsampling
    step = max(1, len(records) // 100)
    load_trend = [
        {
            "timestamp": r["timestamp"],
            "load_kw": round(float(r[primary_metric_name]), 2) if r.get(primary_metric_name) is not None else None,
            "station": r["station"]
        }
        for r in records[::step]
    ]

    temp_vs_load = [
        {
            "temperature_c": round(float(r["temperature"]), 1) if r.get("temperature") is not None else None,
            "load_kw": round(float(r[primary_metric_name]), 2) if r.get(primary_metric_name) is not None else None,
            "station": r["station"]
        }
        for r in records[::step]
        if r.get("temperature") is not None and r.get(primary_metric_name) is not None
    ]

    # Sample anomaly timeline (max 50)
    anomaly_step = max(1, len(anomalies) // 50)
    anomaly_timeline = anomalies[::anomaly_step]

    methodology = (
        "Operational Anomaly Risk is an analytical evaluation based on observed statistical deviations "
        f"(z-score > 2.2 on {primary_metric_name} and thermal excursions). It is not a trained ML failure prediction model."
    )

    return EquipmentHealthAnalytics(
        has_data=True,
        records_analyzed=len(records),
        anomalies_detected=len(anomalies),
        high_risk_signals_count=high_risk_count,
        overall_risk_level=overall_risk,
        has_true_failure_labels=False,
        methodology_note=methodology,
        equipment_records=equipment_records,
        anomaly_timeline=anomaly_timeline,
        load_trend=load_trend,
        temp_vs_load=temp_vs_load,
        missing_fields_notice=missing_notices
    )
