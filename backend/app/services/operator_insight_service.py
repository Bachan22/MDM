"""Connected Energy Intelligence & Operator Insight Service for Polar-EMS.

Acts as the unified cross-module orchestrator:
Consumes outputs from:
- energy_analysis_service (historical demand and trend)
- forecasting_service (ML weather-aware load predictions)
- energy_reserve_service (battery reserve status and depletion)
- equipment_health_service (equipment operational signals)
- resource_risk_service (cross-station risk metrics)

Produces:
1. Energy Trend Analysis (Historical/Empirical Truth)
2. Connected Operator Insight (Current -> Forecast -> Operational Consequence -> Action)
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

from ..config import AI_API_ENDPOINT, AI_API_KEY, AI_MODEL
from ..schemas.mdm_models import (
    EnergyTrendAnalysis,
    OperatorInsightResponse,
)
from .energy_analysis_service import calculate_energy_analytics
from .energy_reserve_service import calculate_energy_reserve_analytics
from .equipment_health_service import calculate_equipment_health_analytics
from .forecasting_service import generate_weather_load_forecast
from .mdm_storage_service import get_mdm_status, query_mdm_records
from .operational_context_service import build_operational_context
from .resource_risk_service import calculate_station_resource_risk

logger = logging.getLogger("polar_ems.operator_insight")


def calculate_energy_trend_analysis(
    station: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> EnergyTrendAnalysis:
    """Computes quantitative historical energy behavior and contribution breakdowns."""
    status = get_mdm_status()
    if not status.has_data:
        return EnergyTrendAnalysis(
            has_data=False,
            trend_summary="No telemetry data currently uploaded to analyze historical energy trends."
        )

    energy_res = calculate_energy_analytics(station, start_date, end_date)
    if not energy_res.has_data:
        return EnergyTrendAnalysis(
            has_data=False,
            trend_summary="No energy records match the active filter criteria."
        )

    records = query_mdm_records(station=station, start_date=start_date, end_date=end_date)
    records.sort(key=lambda r: (r.get("timestamp") or "", r.get("ts") or 0))

    consumptions = [float(r.get("energy_consumption") or r.get("equipment_load") or 0.0) for r in records if (r.get("energy_consumption") is not None or r.get("equipment_load") is not None)]
    if not consumptions:
        consumptions = [0.0]

    avg_kw = round(sum(consumptions) / max(1, len(consumptions)), 1)
    peak_kw = round(max(consumptions), 1)
    min_kw = round(min(consumptions), 1)

    demand_stress_pct = round(((peak_kw - avg_kw) / max(0.1, avg_kw)) * 100.0, 1)

    # Station Contribution Shares
    station_shares: Dict[str, float] = {}
    total_net_kwh = sum(energy_res.consumption_by_station.values()) if energy_res.consumption_by_station else 0.0
    highest_st: Optional[str] = None
    max_share = -1.0

    if total_net_kwh > 0:
        for st_name, val in energy_res.consumption_by_station.items():
            pct = round((val / total_net_kwh) * 100.0, 1)
            station_shares[st_name] = pct
            if pct > max_share:
                max_share = pct
                highest_st = st_name
    elif station and station.lower() not in ("all", "all stations"):
        highest_st = station
        station_shares[station] = 100.0

    # Equipment Load Contribution / Association
    eq_records = [float(r["equipment_load"]) for r in records if r.get("equipment_load") is not None]
    eq_change_pct: Optional[float] = None
    eq_note: Optional[str] = None
    if len(eq_records) >= 24:
        half_eq = len(eq_records) // 2
        eq1 = sum(eq_records[:half_eq]) / half_eq
        eq2 = sum(eq_records[half_eq:]) / len(eq_records[half_eq:])
        if eq1 > 0:
            eq_change_pct = round(((eq2 - eq1) / eq1) * 100.0, 1)
            if eq_change_pct > 3.0:
                eq_note = f"Higher equipment load (+{eq_change_pct}%) is associated with the observed increase in station demand."
            elif eq_change_pct < -3.0:
                eq_note = f"Lower equipment load ({eq_change_pct}%) is associated with reduced station demand."
            else:
                eq_note = "Equipment load profiles remain steady across the observed period."
    elif eq_records:
        eq_note = "Equipment telemetry observed without significant baseline shift."

    # Historical trend summary narrative
    trend_dir = energy_res.trend_direction or "Stable"
    trend_pct = energy_res.trend_pct or 0.0
    st_context = f"at {station}" if (station and station.lower() not in ("all", "all stations")) else (f"with {highest_st} contributing {max_share}% of demand" if highest_st else "")

    if trend_dir == "Increasing":
        summary = f"Energy consumption is increasing by +{trend_pct}% relative to the previous period {st_context}. Peak demand reaches {peak_kw} kW (+{demand_stress_pct}% above average baseload)."
    elif trend_dir == "Decreasing":
        summary = f"Energy consumption decreased by {abs(trend_pct)}% across the period {st_context}. Operational baseload averaged {avg_kw} kW with a maximum peak of {peak_kw} kW."
    else:
        summary = f"Energy consumption remained steady ({trend_pct:+.1f}%) across the observed window {st_context}, maintaining an average demand of {avg_kw} kW."

    return EnergyTrendAnalysis(
        has_data=True,
        consumption_trend_pct=trend_pct,
        consumption_trend_direction=trend_dir,
        average_demand_kw=avg_kw,
        peak_demand_kw=peak_kw,
        min_demand_kw=min_kw,
        demand_stress_pct=demand_stress_pct,
        highest_consuming_station=highest_st,
        station_shares=station_shares,
        equipment_load_change_pct=eq_change_pct,
        equipment_association_note=eq_note,
        trend_summary=summary
    )


def generate_operator_insight(
    station: Optional[str] = None,
    anchor_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    horizon: int = 24,
    policy_override: Optional[Dict[str, Any]] = None
) -> OperatorInsightResponse:
    """
    Synthesizes cross-module operational state from existing services into a connected insight.
    Evaluates:
    1. Historical Energy Trend (energy_analysis_service)
    2. Weather Load ML Forecast (forecasting_service)
    3. Battery & Renewable Reserves (energy_reserve_service)
    4. Equipment Operational Signals (equipment_health_service)
    5. Station Resource Risks (resource_risk_service)
    """
    status = get_mdm_status()
    target_station = station if (station and station.lower() not in ("all", "all stations")) else (status.stations[0] if status.stations else "Bharati")

    if not status.has_data:
        return OperatorInsightResponse(
            status="data_required",
            station=station or "All",
            anchor_date=anchor_date,
            forecast_horizon_hours=horizon,
            priority_level=7,
            priority_title="Dataset Required",
            energy_status="NORMAL",
            trend_analysis=EnergyTrendAnalysis(has_data=False, trend_summary="No dataset uploaded."),
            current_situation="No station telemetry dataset is currently loaded.",
            forecast_impact="Telemetry records are required to generate weather-aware load forecasts.",
            operational_consequence="Reserve status and operational risk cannot be determined without station data.",
            recommended_actions=["Upload a telemetry dataset in Data Management to activate connected energy analytics."],
            source="Connected Energy Intelligence Engine"
        )

    # 1. Historical Trend Analysis
    trend_analysis = calculate_energy_trend_analysis(station=station, start_date=start_date, end_date=end_date)

    # 2. Canonical Operational Context (Single source of truth)
    unified_context = build_operational_context(
        station=target_station,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
        horizon=horizon,
        policy_override=policy_override
    )

    energy_ctx = unified_context.get("energy", {})
    fc_ctx = unified_context.get("forecast", {})
    weather_ctx = unified_context.get("weather", {})
    renewable_ctx = unified_context.get("renewable", {})
    battery_ctx = unified_context.get("battery", {})
    risk_ctx = unified_context.get("resource_risk", {})

    # Extract canonical metrics
    cur_load_kw = energy_ctx.get("current_load_kw", trend_analysis.average_demand_kw or 40.0)
    avg_24h_kw = energy_ctx.get("recent_average_kw", trend_analysis.average_demand_kw or 40.0)
    fc_avg_kw = fc_ctx.get("forecast_average_kw", avg_24h_kw)
    fc_peak_kw = fc_ctx.get("forecast_peak_kw", avg_24h_kw * 1.2)
    fc_time = fc_ctx.get("peak_timestamp", "18:00")
    change_pct = fc_ctx.get("change_vs_baseline_pct", 0.0)

    reserve_pct = battery_ctx.get("reserve_pct")
    reserve_trend = battery_ctx.get("trend", "stable")
    days_rem = battery_ctx.get("estimated_days_remaining")
    battery_avail = battery_ctx.get("battery_available", False)

    ren_contrib_pct = renewable_ctx.get("share_pct", 0.0)
    crit_win = fc_ctx.get("critical_window")
    chg_opp = fc_ctx.get("charging_opportunity")

    # 3. Priority Evaluation (1 to 7)
    priority_level = 7
    priority_title = "Normal Operating Conditions"
    energy_status = "NORMAL"

    # Evaluate using forecast_adjusted_status from unified operational context
    fc_status = risk_ctx.get("forecast_adjusted_status", "NORMAL")
    if fc_status == "CRITICAL":
        priority_level = 1
        priority_title = "Critical Energy Reserve Constraint"
        energy_status = "CRITICAL"
    elif change_pct > 15.0 or (crit_win and crit_win.get("severity") == "HIGH"):
        priority_level = 2
        priority_title = "Projected High-Demand Peak Window"
        energy_status = "CONSERVE" if fc_status in ("CONSERVE", "CRITICAL") else "WATCH"
    elif trend_analysis.consumption_trend_direction == "Increasing" and (trend_analysis.consumption_trend_pct or 0) > 8.0:
        priority_level = 3
        priority_title = "Accelerating Demand Escalation"
        energy_status = "WATCH"
    elif reserve_trend in ("declining", "rapidly declining"):
        priority_level = 4
        priority_title = "Declining Stored Reserve Buffer"
        energy_status = "WATCH"
    elif ren_contrib_pct < 20.0 and change_pct > 5.0:
        priority_level = 5
        priority_title = "Renewable Generation Deficit"
        energy_status = "WATCH"
    elif trend_analysis.equipment_load_change_pct is not None and trend_analysis.equipment_load_change_pct > 12.0:
        priority_level = 6
        priority_title = "Elevated Equipment Auxiliary Load"
        energy_status = "WATCH"
    else:
        priority_level = 7
        priority_title = "Normal Operating Conditions"
        energy_status = "NORMAL"

    # 4. Deterministic 4-Step Operational Narrative Construction
    # Step A: Current Situation
    if trend_analysis.consumption_trend_direction == "Increasing":
        cur_sit = f"Energy demand at {target_station} is currently trending upward at {cur_load_kw} kW (+{trend_analysis.consumption_trend_pct}% vs prior period, 24h baseline: {avg_24h_kw} kW)."
    elif trend_analysis.consumption_trend_direction == "Decreasing":
        cur_sit = f"Energy demand at {target_station} is easing at {cur_load_kw} kW ({trend_analysis.consumption_trend_pct}% vs prior period, baseload: {avg_24h_kw} kW)."
    else:
        cur_sit = f"Station electrical demand at {target_station} is stable at {cur_load_kw} kW, closely tracking the baseline average of {avg_24h_kw} kW."

    # Step B: Forecast Impact
    if change_pct > 8.0:
        fc_imp = f"The weather-aware ML load forecast indicates an additional demand surge averaging {fc_avg_kw} kW (+{change_pct}%), peaking at {fc_peak_kw} kW around {fc_time}."
    elif change_pct < -5.0:
        fc_imp = f"The weather-aware load forecast indicates demand easing to an average of {fc_avg_kw} kW ({change_pct}%), with maximum excursion limited to {fc_peak_kw} kW."
    else:
        fc_imp = f"The weather-aware load forecast indicates steady demand averaging {fc_avg_kw} kW over the next {horizon} hours, reaching a peak of {fc_peak_kw} kW at {fc_time}."

    # Step C: Operational Consequence
    conseq_parts = []
    if energy_status in ("CRITICAL", "CONSERVE"):
        if battery_avail and reserve_pct is not None:
            conseq_parts.append(f"Available battery reserve ({reserve_pct}% SoC" + (f", ~{days_rem} days support)" if days_rem else ")") + f" is under increased pressure during the projected {crit_win.get('window', 'peak window') if crit_win else 'peak window'}")
        else:
            conseq_parts.append("Projected peak demand exceeds standard operating buffers, increasing reliance on primary generation")
    elif energy_status == "WATCH":
        if crit_win:
            conseq_parts.append(f"Elevated demand during {crit_win.get('window', 'the peak window')} may reduce operating reserves if baseload continues to rise")
        else:
            conseq_parts.append("Upcoming demand shifts require active monitoring of spinning reserve and battery state of charge")
    else:
        if chg_opp:
            conseq_parts.append(f"Favorable energy balance during {chg_opp.get('window', 'off-peak hours')} provides an opportunity to stabilize battery reserves")
        else:
            conseq_parts.append("Generation availability and current reserves are sufficient to sustain standard operational schedules")

    op_conseq = ". ".join(conseq_parts) + "."

    # Step D: Recommended Actions
    actions: List[str] = []
    if energy_status == "CRITICAL":
        actions.append("Protect Tier 1 critical life-support and emergency communication infrastructure.")
        actions.append("Defer non-critical auxiliary and Tier 4 discretionary loads during the projected peak.")
        actions.append("Preserve battery reserve buffer and verify primary generator dispatch availability.")
    elif energy_status == "CONSERVE":
        win_label = crit_win.get("window", "the peak window") if crit_win else "the peak window"
        actions.append(f"Maintain additional battery reserve buffer prior to {win_label}.")
        actions.append("Defer non-critical Tier 4 auxiliary loads during the projected peak period.")
        if chg_opp:
            actions.append(f"Leverage the {chg_opp.get('window')} to rebuild battery storage.")
    elif energy_status == "WATCH":
        win_label = crit_win.get("window", "the projected peak") if crit_win else "the projected peak"
        actions.append(f"Maintain the existing reserve operating buffer and monitor telemetry ahead of {win_label}.")
        actions.append("Review high-load equipment before applying broader conservation measures.")
        if chg_opp:
            actions.append("Utilize lower demand windows to stabilize stored energy reserves.")
    else:
        actions.append("Maintain standard dispatch and nominal operating reserve buffers.")
        if chg_opp:
            actions.append(f"Utilize the {chg_opp.get('window')} to optimize energy storage.")

    # 5. Live AI Call Enhancement with Deterministic Safeguards
    if AI_API_KEY and not AI_API_KEY.startswith("YOUR_"):
        system_prompt = (
            "You are the POLAR-EMS Antarctic Station Energy Operations Analyst. "
            "Synthesize the connected station energy trend, ML load forecast, battery reserve, and risk state. "
            "CRITICAL INSTRUCTIONS:\n"
            "1. Ground all claims strictly in provided facts. Do not invent numbers or fake weather events.\n"
            "2. ML forecast predicts electrical power demand, NOT weather.\n"
            "3. Connect: Historical Energy Trend -> ML Forecast -> Operational Consequence -> Practical Operator Actions.\n"
            "4. Do NOT recommend unsupported commands (e.g. do not order direct equipment shutdowns).\n"
            "5. Output strict JSON with keys: current_situation, forecast_impact, operational_consequence, recommended_actions (array)."
        )

        user_content = json.dumps({
            "station": target_station,
            "horizon_hours": horizon,
            "priority_level": priority_level,
            "energy_status": energy_status,
            "trend_analysis": {
                "trend_pct": trend_analysis.consumption_trend_pct,
                "direction": trend_analysis.consumption_trend_direction,
                "demand_stress_pct": trend_analysis.demand_stress_pct,
                "equipment_note": trend_analysis.equipment_association_note
            },
            "current_energy": energy_ctx,
            "forecast": fc_ctx,
            "weather": weather_ctx,
            "renewable": renewable_ctx,
            "battery": battery_ctx,
            "critical_window": crit_win,
            "charging_opportunity": chg_opp
        }, indent=2)

        try:
            req = urllib.request.Request(
                AI_API_ENDPOINT,
                data=json.dumps({
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Generate connected operator insight:\n{user_content}"}
                    ],
                    "temperature": 0.15,
                    "response_format": {"type": "json_object"}
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                if resp.status == 200:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    parsed = json.loads(resp_json["choices"][0]["message"]["content"])
                    llm_sit = str(parsed.get("current_situation") or cur_sit).strip()
                    llm_fc = str(parsed.get("forecast_impact") or fc_imp).strip()
                    llm_conseq = str(parsed.get("operational_consequence") or op_conseq).strip()
                    llm_acts = parsed.get("recommended_actions")
                    if not isinstance(llm_acts, list) or not llm_acts:
                        llm_acts = actions

                    return OperatorInsightResponse(
                        status="success",
                        station=target_station,
                        anchor_date=anchor_date,
                        forecast_horizon_hours=horizon,
                        priority_level=priority_level,
                        priority_title=priority_title,
                        energy_status=energy_status,
                        trend_analysis=trend_analysis,
                        current_situation=llm_sit,
                        forecast_impact=llm_fc,
                        operational_consequence=llm_conseq,
                        recommended_actions=llm_acts,
                        underlying_metrics={
                            "current_load_kw": cur_load_kw,
                            "average_24h_kw": avg_24h_kw,
                            "forecast_peak_kw": fc_peak_kw,
                            "forecast_avg_kw": fc_avg_kw,
                            "battery_reserve_pct": reserve_pct,
                            "estimated_days_remaining": days_rem,
                            "renewable_contribution_pct": ren_contrib_pct
                        },
                        signal_availability={
                            "solar": renewable_ctx.get("solar_status", "Unavailable"),
                            "wind": renewable_ctx.get("wind_status", "Unavailable"),
                            "battery": "Observed" if battery_avail else "Unavailable",
                            "weather": "Observed" if weather_ctx.get("temperature_c") is not None else "Unavailable",
                            "load_forecast": "Forecasted (XGBoost)"
                        },
                        missing_data_notices=unified_context.get("missing_notices", []),
                        source=f"Connected AI Analyst ({AI_MODEL})"
                    )
        except Exception as e:
            logger.warning(f"Live AI operator insight error, using fallback: {e}")

    # Deterministic Grounded Output
    return OperatorInsightResponse(
        status="fallback",
        station=target_station,
        anchor_date=anchor_date,
        forecast_horizon_hours=horizon,
        priority_level=priority_level,
        priority_title=priority_title,
        energy_status=energy_status,
        trend_analysis=trend_analysis,
        current_situation=cur_sit,
        forecast_impact=fc_imp,
        operational_consequence=op_conseq,
        recommended_actions=actions,
        underlying_metrics={
            "current_load_kw": cur_load_kw,
            "average_24h_kw": avg_24h_kw,
            "forecast_peak_kw": fc_peak_kw,
            "forecast_avg_kw": fc_avg_kw,
            "battery_reserve_pct": reserve_pct,
            "estimated_days_remaining": days_rem,
            "renewable_contribution_pct": ren_contrib_pct
        },
        signal_availability={
            "solar": renewable_ctx.get("solar_status", "Unavailable"),
            "wind": renewable_ctx.get("wind_status", "Unavailable"),
            "battery": "Observed" if battery_avail else "Unavailable",
            "weather": "Observed" if weather_ctx.get("temperature_c") is not None else "Unavailable",
            "load_forecast": "Forecasted (XGBoost)"
        },
        missing_data_notices=unified_context.get("missing_notices", []),
        source="Connected Energy Intelligence Engine"
    )
