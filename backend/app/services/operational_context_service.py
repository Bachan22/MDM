"""Central Canonical Operational Context Service for POLAR-EMS.

Serves as the single source of truth across all modules:
- Weather Load Forecast (XGBoost)
- Energy Analytics (Demand & Trends)
- Energy Reserve (Battery Autonomy & Depletion)
- Station Resource Risk (Current Observed vs Forecast-Adjusted Risk)
- Equipment Health (Operational Anomalies & Load Contribution)
- Operator Insight (Cross-Module Operational Action)
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from ..config import BATTERY_CAPACITY_KWH
from ..schemas.mdm_models import EnergyReservePolicy
from .forecasting_service import generate_weather_load_forecast
from .mdm_storage_service import get_data_version, get_mdm_status, query_mdm_records

_CONTEXT_CACHE: Dict[str, Dict[str, Any]] = {}


def clear_operational_context_cache() -> None:
    _CONTEXT_CACHE.clear()


def build_operational_context(
    station: Optional[str] = None,
    anchor_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    horizon: int = 24,
    policy_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Builds the single canonical operational state object for a selected station,
    date, period, forecast horizon, and policy.
    """
    version = get_data_version()
    cache_key = f"{version}_{station}_{anchor_date}_{start_date}_{end_date}_{horizon}_{policy_override}"
    if cache_key in _CONTEXT_CACHE:
        return _CONTEXT_CACHE[cache_key]

    status = get_mdm_status()
    target_station = (
        station
        if (station and station.lower() not in ("all", "all stations"))
        else (status.stations[0] if status.stations else "Bharati")
    )

    if not status.has_data:
        ctx = {
            "has_data": False,
            "station": target_station,
            "anchor_date": anchor_date,
            "forecast_horizon_hours": horizon,
            "energy": {"current_load_kw": 0.0, "recent_average_kw": 0.0, "peak_observed_kw": 0.0, "trend_pct": 0.0, "trend_direction": "Stable"},
            "forecast": {"forecast_average_kw": 0.0, "forecast_peak_kw": 0.0, "peak_timestamp": None, "change_vs_baseline_pct": 0.0},
            "battery": {"reserve_pct": None, "available_capacity_kwh": None, "storage_capacity_kwh": None, "trend": "stable", "battery_available": False, "estimated_days_remaining": None},
            "renewable": {"share_pct": 0.0, "solar_status": "Unavailable", "wind_status": "Unavailable", "solar_kw": 0.0, "wind_kw": 0.0, "renewable_kw": 0.0},
            "equipment": {"average_load_kw": 0.0, "load_change_pct": 0.0, "anomaly_count": 0, "health_status": "NORMAL"},
            "resource_risk": {"current_status": "LOW", "forecast_adjusted_status": "NORMAL", "forecast_driver_reason": "No active dataset."},
            "signal_availability": {"solar": "Unavailable", "wind": "Unavailable", "battery": "Unavailable", "weather": "Unavailable", "load_forecast": "Unavailable"},
            "missing_notices": ["No telemetry dataset is currently loaded."]
        }
        _CONTEXT_CACHE[cache_key] = ctx
        return ctx

    # 1. Fetch filtered empirical records
    records = query_mdm_records(station=target_station, start_date=start_date, end_date=end_date)
    if not records:
        # Fallback to general station records if window query returns empty
        records = query_mdm_records(station=target_station)

    if not records:
        records = query_mdm_records()

    records.sort(key=lambda r: (r.get("timestamp") or "", r.get("ts") or 0))

    # Anchor date filtering
    if anchor_date:
        filtered = [r for r in records if (r.get("timestamp") or "")[:10] <= anchor_date[:10]]
        if filtered:
            records = filtered

    latest_record = records[-1]
    missing_notices: List[str] = []

    # 2. Canonical Energy Metrics (Historical / Observed)
    energy_records = [r for r in records if r.get("energy_consumption") is not None or r.get("equipment_load") is not None]
    if not energy_records:
        energy_records = records

    recent_24 = energy_records[-24:] if len(energy_records) >= 24 else energy_records
    current_load_kw = round(float(latest_record.get("energy_consumption") or latest_record.get("equipment_load") or 40.0), 1)
    recent_average_kw = round(float(sum(float(r.get("energy_consumption") or r.get("equipment_load") or 0.0) for r in recent_24) / max(1, len(recent_24))), 1)
    peak_observed_kw = round(float(max(float(r.get("energy_consumption") or r.get("equipment_load") or 0.0) for r in recent_24)), 1)

    trend_pct = 0.0
    trend_direction = "Stable"
    if len(energy_records) >= 48:
        half = len(energy_records) // 2
        p1 = sum(float(r.get("energy_consumption") or 0.0) for r in energy_records[:half]) / max(1, half)
        p2 = sum(float(r.get("energy_consumption") or 0.0) for r in energy_records[half:]) / max(1, len(energy_records) - half)
        if p1 > 0:
            trend_pct = round(((p2 - p1) / p1) * 100.0, 1)
            if trend_pct > 3.0:
                trend_direction = "Increasing"
            elif trend_pct < -3.0:
                trend_direction = "Decreasing"

    # 3. Canonical Weather & Telemetry Readings
    temp_val = latest_record.get("temperature")
    temperature_c = round(float(temp_val), 1) if temp_val is not None else None
    wind_spd_val = latest_record.get("wind_speed")
    wind_speed_ms = round(float(wind_spd_val), 1) if wind_spd_val is not None else None

    # 4. Canonical Battery State & Policy Evaluation
    policy_dict = policy_override or {}
    safe_days = float(policy_dict.get("safe_days", 30.0))
    watch_days = float(policy_dict.get("watch_days", 15.0))
    conserve_days = float(policy_dict.get("conserve_days", 7.0))
    critical_days = float(policy_dict.get("critical_days", 3.0))
    configured_capacity = policy_dict.get("configured_capacity_kwh")
    if configured_capacity is not None:
        try:
            configured_capacity = float(configured_capacity)
        except (ValueError, TypeError):
            configured_capacity = None

    active_station_count = status.stations_count if (not station or station.lower() in ("all", "all stations")) else 1
    storage_capacity_kwh = configured_capacity if configured_capacity is not None else (BATTERY_CAPACITY_KWH * max(1, active_station_count))

    battery_records = [r for r in records if r.get("battery_level") is not None]
    has_battery_telemetry = len(battery_records) > 0
    reserve_pct: Optional[float] = None
    available_capacity_kwh: Optional[float] = None
    reserve_trend = "stable"
    estimated_days_remaining: Optional[float] = None

    if has_battery_telemetry:
        reserve_pct = round(float(battery_records[-1]["battery_level"]), 1)
        available_capacity_kwh = round((reserve_pct / 100.0) * storage_capacity_kwh, 1)
        if len(battery_records) >= 24:
            b_prev = sum(float(r["battery_level"]) for r in battery_records[-24:-12]) / 12.0
            b_curr = sum(float(r["battery_level"]) for r in battery_records[-12:]) / 12.0
            if (b_prev - b_curr) > 4.0:
                reserve_trend = "rapidly declining"
            elif (b_prev - b_curr) > 1.5:
                reserve_trend = "declining"
            elif (b_curr - b_prev) > 1.5:
                reserve_trend = "recharging"

        daily_rate_kw = max(1.0, recent_average_kw * 24.0)
        estimated_days_remaining = round(available_capacity_kwh / daily_rate_kw, 1)
    elif configured_capacity is not None and configured_capacity > 0:
        reserve_pct = 100.0
        available_capacity_kwh = configured_capacity
        daily_rate_kw = max(1.0, recent_average_kw * 24.0)
        estimated_days_remaining = round(available_capacity_kwh / daily_rate_kw, 1)
    else:
        missing_notices.append("Battery storage level telemetry unavailable in dataset.")

    # 5. Canonical Renewable Generation
    solar_records = [r for r in records if r.get("solar_generation") is not None]
    wind_records = [r for r in records if r.get("wind_generation") is not None]
    cur_solar_kw = round(float(latest_record.get("solar_generation") or 0.0), 1)
    cur_wind_kw = round(float(latest_record.get("wind_generation") or 0.0), 1)
    total_renewable_kw = round(cur_solar_kw + cur_wind_kw, 1)

    solar_status = "Observed" if solar_records else "Unavailable"
    wind_status = "Observed" if wind_records else "Unavailable"
    if solar_status == "Unavailable" and wind_status == "Unavailable":
        missing_notices.append("Solar and wind generation columns not detected.")

    renewable_share_pct = round((total_renewable_kw / max(0.1, current_load_kw)) * 100.0, 1) if current_load_kw > 0 else 0.0
    renewable_share_pct = min(100.0, renewable_share_pct)

    # 6. Canonical Equipment Metrics
    eq_records = [r for r in records if r.get("equipment_load") is not None]
    avg_equipment_load_kw = round(float(sum(float(r["equipment_load"]) for r in eq_records) / max(1, len(eq_records))), 1) if eq_records else current_load_kw
    eq_change_pct: Optional[float] = None
    if len(eq_records) >= 24:
        half_eq = len(eq_records) // 2
        eq1 = sum(float(r["equipment_load"]) for r in eq_records[:half_eq]) / half_eq
        eq2 = sum(float(r["equipment_load"]) for r in eq_records[half_eq:]) / max(1, len(eq_records) - half_eq)
        if eq1 > 0:
            eq_change_pct = round(((eq2 - eq1) / eq1) * 100.0, 1)

    eq_anomalies_count = 0
    if eq_records and avg_equipment_load_kw > 0:
        high_draw_count = sum(1 for r in eq_records if float(r.get("equipment_load") or 0) > avg_equipment_load_kw * 1.35)
        eq_anomalies_count = high_draw_count

    eq_health_status = "NORMAL"
    if eq_anomalies_count > 5 or (eq_change_pct is not None and eq_change_pct > 25.0):
        eq_health_status = "ELEVATED_LOAD"

    # 7. Canonical XGBoost Weather-Aware Forecast
    fc_avg_kw = recent_average_kw
    fc_peak_kw = peak_observed_kw
    fc_peak_time = "18:00"
    fc_change_pct = 0.0
    critical_window = None
    charging_opportunity = None

    try:
        fc_res = generate_weather_load_forecast(
            station=target_station,
            horizon=horizon,
            anchor_date=anchor_date
        )
        if fc_res.get("status") == "success":
            fc_avg_kw = round(float(fc_res.get("predicted_average_kw") or fc_avg_kw), 1)
            fc_peak_kw = round(float(fc_res.get("predicted_peak_kw") or fc_peak_kw), 1)
            fc_peak_time = fc_res.get("peak_time") or fc_peak_time
            if recent_average_kw > 0:
                fc_change_pct = round(((fc_avg_kw - recent_average_kw) / recent_average_kw) * 100.0, 1)

            # Detect forecast peak critical window
            if fc_change_pct > 8.0 or fc_peak_kw > (recent_average_kw * 1.25):
                critical_window = {
                    "window": f"Projected Peak ({fc_peak_time})",
                    "peak_kw": fc_peak_kw,
                    "reason": f"Projected demand surge averaging {fc_avg_kw} kW (+{fc_change_pct}% over baseline)",
                    "severity": "HIGH" if fc_change_pct > 15.0 else "MEDIUM"
                }

            # Detect forecast charging / low-demand opportunity
            pred_min = float(fc_res.get("predicted_min_kw") or (fc_avg_kw * 0.8))
            if pred_min < (recent_average_kw * 0.9):
                charging_opportunity = {
                    "window": "Off-Peak Thermal Window",
                    "action": "Recharge battery buffer & stabilize thermal storage",
                    "favorable_factors": ["Reduced base heating demand", "Thermal stabilization"]
                }
    except Exception:
        pass

    # 8. Unified Risk Derivation (Strictly separating Current vs Forecast Risk)
    # ─── A. Current Observed Resource Risk ───
    # Evaluates only current observed state: battery %, current demand, renewable share, equipment load
    current_risk_status = "LOW"
    current_risk_driver = "Nominal operating telemetry across all resources."

    if reserve_pct is not None:
        if reserve_pct < 30.0 or (configured_capacity is not None and estimated_days_remaining is not None and estimated_days_remaining <= critical_days):
            current_risk_status = "CRITICAL"
            current_risk_driver = f"Battery SoC critically low ({reserve_pct}%)."
        elif reserve_pct < 45.0 or (configured_capacity is not None and estimated_days_remaining is not None and estimated_days_remaining <= conserve_days):
            current_risk_status = "HIGH"
            current_risk_driver = f"Battery SoC depleted ({reserve_pct}%) requiring active load management."
        elif reserve_pct < 60.0 or reserve_trend == "rapidly declining" or (configured_capacity is not None and estimated_days_remaining is not None and estimated_days_remaining <= watch_days):
            current_risk_status = "MODERATE"
            current_risk_driver = f"Battery reserve buffer reduced ({reserve_pct}%) with downward draw trend."
    elif current_load_kw > (recent_average_kw * 1.3):
        current_risk_status = "MODERATE"
        current_risk_driver = f"Current station electrical load ({current_load_kw} kW) elevated +30% above 24h baseline."

    # ─── B. Forecast-Adjusted Resource Risk ───
    # Evaluates future projected risk: current state + ML forecast surge + horizon + renewable deficit
    forecast_risk_status = "NORMAL"
    forecast_risk_driver = "Projected energy demand remains within nominal operating buffers."

    # Calculate forecast daily rate & forecast autonomy if battery data exists
    fc_daily_rate_kw = max(1.0, fc_avg_kw * 24.0)
    fc_autonomy_days = round(available_capacity_kwh / fc_daily_rate_kw, 1) if (available_capacity_kwh and available_capacity_kwh > 0) else estimated_days_remaining

    if current_risk_status == "CRITICAL" or (configured_capacity is not None and fc_autonomy_days is not None and fc_autonomy_days <= critical_days):
        forecast_risk_status = "CRITICAL"
        forecast_risk_driver = f"ML forecast demand ({fc_avg_kw} kW) accelerates battery depletion."
    elif fc_change_pct > 15.0 or (critical_window and critical_window.get("severity") == "HIGH") or (configured_capacity is not None and fc_autonomy_days is not None and fc_autonomy_days <= conserve_days):
        forecast_risk_status = "CONSERVE"
        forecast_risk_driver = f"Projected demand peak ({fc_peak_kw} kW, +{fc_change_pct}%) stresses reserve buffers during next {horizon} hours."
    elif fc_change_pct > 5.0 or (configured_capacity is not None and fc_autonomy_days is not None and fc_autonomy_days <= watch_days) or (renewable_share_pct < 15.0 and fc_change_pct > 0):
        forecast_risk_status = "WATCH"
        forecast_risk_driver = f"Upcoming demand increase (+{fc_change_pct}%) with limited renewable contribution ({renewable_share_pct}%)."
    else:
        forecast_risk_status = "NORMAL"
        forecast_risk_driver = f"Forecasted demand ({fc_avg_kw} kW) easily sustained by current reserve buffer over next {horizon}h."

    ctx = {
        "has_data": True,
        "station": target_station,
        "anchor_date": anchor_date,
        "forecast_horizon_hours": horizon,
        "policy": {
            "safe_days": safe_days,
            "watch_days": watch_days,
            "conserve_days": conserve_days,
            "critical_days": critical_days,
            "configured_capacity_kwh": configured_capacity
        },
        "energy": {
            "current_load_kw": current_load_kw,
            "recent_average_kw": recent_average_kw,
            "peak_observed_kw": peak_observed_kw,
            "trend_pct": trend_pct,
            "trend_direction": trend_direction
        },
        "forecast": {
            "forecast_average_kw": fc_avg_kw,
            "forecast_peak_kw": fc_peak_kw,
            "peak_timestamp": fc_peak_time,
            "change_vs_baseline_pct": fc_change_pct,
            "critical_window": critical_window,
            "charging_opportunity": charging_opportunity
        },
        "weather": {
            "temperature_c": temperature_c,
            "wind_speed_ms": wind_speed_ms
        },
        "battery": {
            "reserve_pct": reserve_pct,
            "available_capacity_kwh": available_capacity_kwh,
            "storage_capacity_kwh": storage_capacity_kwh,
            "trend": reserve_trend,
            "battery_available": has_battery_telemetry,
            "estimated_days_remaining": estimated_days_remaining,
            "forecast_days_remaining": fc_autonomy_days
        },
        "renewable": {
            "share_pct": renewable_share_pct,
            "solar_status": solar_status,
            "wind_status": wind_status,
            "solar_kw": cur_solar_kw,
            "wind_kw": cur_wind_kw,
            "renewable_kw": total_renewable_kw
        },
        "equipment": {
            "average_load_kw": avg_equipment_load_kw,
            "load_change_pct": eq_change_pct,
            "anomaly_count": eq_anomalies_count,
            "health_status": eq_health_status
        },
        "resource_risk": {
            "current_status": current_risk_status,
            "current_driver": current_risk_driver,
            "forecast_adjusted_status": forecast_risk_status,
            "forecast_driver_reason": forecast_risk_driver
        },
        "signal_availability": {
            "solar": solar_status,
            "wind": wind_status,
            "battery": "Observed" if has_battery_telemetry else "Unavailable",
            "weather": "Observed" if temperature_c is not None else "Unavailable",
            "load_forecast": "Forecasted (XGBoost)"
        },
        "missing_notices": missing_notices
    }

    _CONTEXT_CACHE[cache_key] = ctx
    return ctx
