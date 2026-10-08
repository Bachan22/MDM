"""Station resource risk evaluation service for Polar-EMS MDM.

Seamlessly connected to the Central Canonical Operational Context:
- Evaluates Current Observed Resource Risk from actual station telemetry.
- Evaluates Forecast-Adjusted Resource Risk from ML load forecast and horizon pressure.
- Explains the exact relationship between current state and forecast future risk.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..schemas.mdm_models import StationResourceRiskAnalytics, StationResourceRiskItem
from .mdm_storage_service import get_data_version, get_mdm_status, query_mdm_records
from .operational_context_service import build_operational_context

_RESOURCE_CACHE: Dict[str, StationResourceRiskAnalytics] = {}


def clear_resource_cache() -> None:
    _RESOURCE_CACHE.clear()


def calculate_station_resource_risk(
    station: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    anchor_date: Optional[str] = None,
    horizon: int = 24,
    policy_override: Optional[Dict[str, Any]] = None
) -> StationResourceRiskAnalytics:
    """Evaluates station resource risk derived from canonical operational context and ML forecast."""
    version = get_data_version()
    cache_key = f"{version}_{station}_{start_date}_{end_date}_{anchor_date}_{horizon}_{policy_override}"
    if cache_key in _RESOURCE_CACHE:
        return _RESOURCE_CACHE[cache_key]

    status = get_mdm_status()
    if not status.has_data:
        res = StationResourceRiskAnalytics(
            has_data=False,
            stations_analyzed=0,
            high_risk_stations_count=0,
            moderate_risk_stations_count=0,
            low_risk_stations_count=0,
            overall_network_risk="LOW",
            network_current_risk="LOW",
            network_forecast_risk="NORMAL",
            forecast_horizon_hours=horizon,
            forecast_summary="No dataset uploaded.",
            missing_fields_notice=["No records found matching filters or no dataset uploaded."]
        )
        _RESOURCE_CACHE[cache_key] = res
        return res

    records = query_mdm_records(station=station, start_date=start_date, end_date=end_date)
    if not records:
        records = query_mdm_records(station=station)

    # Detect available columns across dataset
    has_battery = any(r.get("battery_level") is not None for r in records)
    has_renewable = any(
        r.get("solar_generation") is not None or r.get("wind_generation") is not None or r.get("wind_speed") is not None
        for r in records
    )

    missing_notices = []
    if not has_battery:
        missing_notices.append("Battery storage level data unavailable in uploaded dataset.")
    if not has_renewable:
        missing_notices.append("Renewable generation data unavailable.")

    # Target stations to analyze
    target_stations = (
        [station]
        if (station and station.lower() not in ("all", "all stations"))
        else (sorted(list({r["station"] for r in records if r.get("station")})) or status.stations or ["Bharati"])
    )

    station_risks: List[StationResourceRiskItem] = []
    comparison_chart: List[Dict[str, Any]] = []

    high_risk_count = 0
    moderate_risk_count = 0
    low_risk_count = 0

    highest_forecast_risk_rank = 0  # 0: NORMAL, 1: WATCH, 2: CONSERVE, 3: CRITICAL
    rank_to_status = {0: "NORMAL", 1: "WATCH", 2: "CONSERVE", 3: "CRITICAL"}
    status_to_rank = {"NORMAL": 0, "WATCH": 1, "CONSERVE": 2, "CRITICAL": 3}

    for st in target_stations:
        # Build canonical context for each target station
        st_ctx = build_operational_context(
            station=st,
            anchor_date=anchor_date,
            start_date=start_date,
            end_date=end_date,
            horizon=horizon,
            policy_override=policy_override
        )

        st_energy = st_ctx.get("energy", {})
        st_fc = st_ctx.get("forecast", {})
        st_bat = st_ctx.get("battery", {})
        st_ren = st_ctx.get("renewable", {})
        st_eq = st_ctx.get("equipment", {})
        st_wx = st_ctx.get("weather", {})
        st_res_risk = st_ctx.get("resource_risk", {})

        cur_load = st_energy.get("current_load_kw", 0.0)
        recent_avg_load = st_energy.get("recent_average_kw", 0.0)
        fc_peak = st_fc.get("forecast_peak_kw", cur_load)
        fc_avg = st_fc.get("forecast_average_kw", recent_avg_load)
        fc_change = st_fc.get("change_vs_baseline_pct", 0.0)

        bat_soc = st_bat.get("reserve_pct")
        bat_trend = st_bat.get("trend", "stable")
        bat_days = st_bat.get("estimated_days_remaining")
        bat_fc_days = st_bat.get("forecast_days_remaining")

        temp_c = st_wx.get("temperature_c")
        ren_share = st_ren.get("share_pct", 0.0)

        # ── 1. Battery Reserve Item ──
        if bat_soc is not None:
            # Current Risk (strictly observed)
            if bat_soc < 30.0:
                cur_bat_risk = "CRITICAL"
                cur_bat_driver = f"Battery SoC critically low ({bat_soc}%)"
            elif bat_soc < 45.0:
                cur_bat_risk = "HIGH"
                cur_bat_driver = f"Battery storage depleted ({bat_soc}%)"
            elif bat_soc < 60.0 or bat_trend in ("declining", "rapidly declining"):
                cur_bat_risk = "MODERATE"
                cur_bat_driver = f"Battery reserve buffer reduced ({bat_soc}%, {bat_trend})"
            else:
                cur_bat_risk = "LOW"
                cur_bat_driver = f"Battery storage healthy within normal bounds ({bat_soc}%)"

            # Forecast-Adjusted Risk (current + ML forecast surge over horizon)
            if cur_bat_risk in ("CRITICAL", "HIGH") or (policy_override and bat_fc_days is not None and bat_fc_days <= 3.0):
                fc_bat_risk = "CRITICAL"
                fc_bat_driver = f"ML forecast peak ({fc_peak} kW) rapidly depletes stored reserve within {horizon}h"
            elif fc_change > 12.0 or (policy_override and bat_fc_days is not None and bat_fc_days <= 7.0):
                fc_bat_risk = "CONSERVE"
                fc_bat_driver = f"Projected demand increase (+{fc_change}%) increases reserve drawdown pressure"
            elif fc_change > 5.0 or (policy_override and bat_fc_days is not None and bat_fc_days <= 15.0):
                fc_bat_risk = "WATCH"
                fc_bat_driver = f"Upcoming demand shifts require monitoring of reserve state of charge"
            else:
                fc_bat_risk = "NORMAL"
                fc_bat_driver = f"Sufficient reserve capacity to sustain nominal operations over next {horizon}h"

            evidence = f"Observed SoC: {bat_soc}%. " + (f"ML Forecast ({horizon}h): {fc_avg} kW avg (+{fc_change}%), peak {fc_peak} kW." if fc_change != 0 else "")

            station_risks.append(
                StationResourceRiskItem(
                    station=st,
                    resource="Battery Reserve",
                    risk_level=cur_bat_risk,
                    current_risk_level=cur_bat_risk,
                    forecast_risk_level=fc_bat_risk,
                    main_driver=cur_bat_driver,
                    forecast_driver_reason=fc_bat_driver,
                    current_value=f"{bat_soc}%",
                    historical_average=f"{bat_soc}%",
                    evidence_text=evidence
                )
            )

        # ── 2. Energy Demand & Shortage Item ──
        if recent_avg_load > 0:
            if cur_load > recent_avg_load * 1.3:
                cur_e_risk = "HIGH"
                cur_e_driver = f"Current load ({cur_load} kW) is +30% above 24h baseline"
            elif cur_load > recent_avg_load * 1.1:
                cur_e_risk = "MODERATE"
                cur_e_driver = f"Current load ({cur_load} kW) moderately elevated above baseline"
            else:
                cur_e_risk = "LOW"
                cur_e_driver = f"Current consumption ({cur_load} kW) matches baseline ({recent_avg_load} kW)"

            if fc_change > 15.0:
                fc_e_risk = "CRITICAL"
                fc_e_driver = f"Forecast load surge (+{fc_change}%, peak {fc_peak} kW) creates high demand stress"
            elif fc_change > 5.0:
                fc_e_risk = "WATCH"
                fc_e_driver = f"Forecast demand elevated (+{fc_change}%) over next {horizon}h"
            else:
                fc_e_risk = "NORMAL"
                fc_e_driver = f"Forecast demand ({fc_avg} kW) tracks standard baseline"

            station_risks.append(
                StationResourceRiskItem(
                    station=st,
                    resource="Energy Demand",
                    risk_level=cur_e_risk,
                    current_risk_level=cur_e_risk,
                    forecast_risk_level=fc_e_risk,
                    main_driver=cur_e_driver,
                    forecast_driver_reason=fc_e_driver,
                    current_value=f"{cur_load} kW",
                    historical_average=f"{recent_avg_load} kW",
                    evidence_text=f"Current demand: {cur_load} kW. ML Forecast Peak: {fc_peak} kW (+{fc_change}%)."
                )
            )

        # ── 3. Renewable Generation Coverage Item ──
        if has_renewable:
            cur_ren_risk = "LOW" if ren_share >= 25.0 else ("MODERATE" if ren_share >= 10.0 else "HIGH")
            fc_ren_risk = "NORMAL" if ren_share >= 25.0 else ("WATCH" if ren_share >= 10.0 else "CONSERVE")
            station_risks.append(
                StationResourceRiskItem(
                    station=st,
                    resource="Renewable Coverage",
                    risk_level=cur_ren_risk,
                    current_risk_level=cur_ren_risk,
                    forecast_risk_level=fc_ren_risk,
                    main_driver=f"Renewable share provides {ren_share}% of active station demand",
                    forecast_driver_reason="Low solar/wind generation shifts load onto storage and generation dispatch" if ren_share < 15.0 else "Adequate renewable contribution expected",
                    current_value=f"{ren_share}%",
                    historical_average=f"{ren_share}%",
                    evidence_text=f"Observed solar & wind contribution: {ren_share}%."
                )
            )

        # ── 4. Environmental Stress Item ──
        if temp_c is not None:
            cur_env_risk = "HIGH" if temp_c < -30.0 else ("MODERATE" if temp_c < -20.0 else "LOW")
            station_risks.append(
                StationResourceRiskItem(
                    station=st,
                    resource="Environmental Stress",
                    risk_level=cur_env_risk,
                    current_risk_level=cur_env_risk,
                    forecast_risk_level=cur_env_risk,
                    main_driver=f"Sub-zero thermal environment ({temp_c}°C) drives heating loads",
                    forecast_driver_reason=f"Extreme cold ambient condition ({temp_c}°C) sustains high heating requirement",
                    current_value=f"{temp_c}°C",
                    historical_average=f"{temp_c}°C",
                    evidence_text=f"Station ambient temperature observed at {temp_c}°C."
                )
            )

        # Station summary evaluation
        st_cur_status = st_res_risk.get("current_status", "LOW")
        st_fc_status = st_res_risk.get("forecast_adjusted_status", "NORMAL")

        if st_cur_status in ("HIGH", "CRITICAL"):
            high_risk_count += 1
        elif st_cur_status == "MODERATE":
            moderate_risk_count += 1
        else:
            low_risk_count += 1

        fc_rank = status_to_rank.get(st_fc_status, 0)
        if fc_rank > highest_forecast_risk_rank:
            highest_forecast_risk_rank = fc_rank

        comparison_chart.append({
            "station": st,
            "overall_risk": st_cur_status,
            "current_risk": st_cur_status,
            "forecast_risk": st_fc_status,
            "current_energy_kw": cur_load,
            "avg_energy_kw": recent_avg_load,
            "forecast_peak_kw": fc_peak,
            "forecast_avg_kw": fc_avg,
            "current_battery_soc": bat_soc,
            "recent_battery_soc": bat_soc,
            "battery_soc": bat_soc,
            "avg_battery_soc": bat_soc,
            "renewable_share_pct": ren_share,
            "avg_temperature_c": temp_c,
            "temperature_c": temp_c
        })

    # Network-wide rollup
    network_current = "HIGH" if high_risk_count > 0 else ("MODERATE" if moderate_risk_count > 0 else "LOW")
    network_forecast = rank_to_status.get(highest_forecast_risk_rank, "NORMAL")

    # Forecast summary
    if network_forecast in ("CRITICAL", "CONSERVE"):
        fc_summary = f"Forecast-adjusted resource risk is {network_forecast} over the next {horizon}h due to projected peak load surges and reserve drawdown."
    elif network_forecast == "WATCH":
        fc_summary = f"Forecast-adjusted resource risk is WATCH over the next {horizon}h due to moderate upcoming demand shifts."
    else:
        fc_summary = f"Forecast-adjusted resource risk is NORMAL over the next {horizon}h with stable projected demand and adequate operating buffers."

    res = StationResourceRiskAnalytics(
        has_data=True,
        stations_analyzed=len(target_stations),
        high_risk_stations_count=high_risk_count,
        moderate_risk_stations_count=moderate_risk_count,
        low_risk_stations_count=low_risk_count,
        overall_network_risk=network_current,
        network_current_risk=network_current,
        network_forecast_risk=network_forecast,
        forecast_horizon_hours=horizon,
        forecast_summary=fc_summary,
        station_risks=station_risks,
        station_risk_comparison=comparison_chart,
        battery_available=has_battery,
        renewable_available=has_renewable,
        missing_fields_notice=missing_notices
    )

    _RESOURCE_CACHE[cache_key] = res
    return res
