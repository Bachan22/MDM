"""Station resource risk evaluation service for Polar-EMS MDM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..schemas.mdm_models import StationResourceRiskAnalytics, StationResourceRiskItem
from .mdm_storage_service import query_mdm_records


def calculate_station_resource_risk(
    station: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> StationResourceRiskAnalytics:
    """Evaluates station resource risk derived from actual uploaded operational data."""
    records = query_mdm_records(station=station, start_date=start_date, end_date=end_date)

    if not records:
        return StationResourceRiskAnalytics(
            has_data=False,
            stations_analyzed=0,
            high_risk_stations_count=0,
            moderate_risk_stations_count=0,
            low_risk_stations_count=0,
            overall_network_risk="LOW",
            missing_fields_notice=["No records found matching filters or no dataset uploaded."]
        )

    # Detect available columns
    has_battery = any(r.get("battery_level") is not None for r in records)
    has_renewable = any(
        r.get("solar_generation") is not None or r.get("wind_generation") is not None or r.get("wind_speed") is not None
        for r in records
    )
    has_temp = any(r.get("temperature") is not None for r in records)
    has_energy = any(r.get("energy_consumption") is not None for r in records)

    missing_notices = []
    if not has_battery:
        missing_notices.append("Battery storage level data unavailable in uploaded dataset.")
    if not has_renewable:
        missing_notices.append("Renewable generation data unavailable.")

    # Group by station
    stations = sorted(list({r["station"] for r in records}))
    station_risks: List[StationResourceRiskItem] = []
    comparison_chart: List[Dict[str, Any]] = []

    high_risk_stations = 0
    moderate_risk_stations = 0
    low_risk_stations = 0

    for st in stations:
        st_records = [r for r in records if r["station"] == st]
        if not st_records:
            continue

        # Energy consumption analysis
        e_vals = [float(r["energy_consumption"]) for r in st_records if r.get("energy_consumption") is not None]
        avg_energy = (sum(e_vals) / len(e_vals)) if e_vals else 0.0
        recent_e_vals = e_vals[-(max(1, len(e_vals) // 4)):] if e_vals else []
        recent_avg_energy = (sum(recent_e_vals) / len(recent_e_vals)) if recent_e_vals else avg_energy

        # Battery analysis
        bat_vals = [float(r["battery_level"]) for r in st_records if r.get("battery_level") is not None]
        avg_bat = (sum(bat_vals) / len(bat_vals)) if bat_vals else None
        recent_bat_vals = bat_vals[-(max(1, len(bat_vals) // 4)):] if bat_vals else []
        recent_avg_bat = (sum(recent_bat_vals) / len(recent_bat_vals)) if recent_bat_vals else avg_bat

        # Temperature analysis
        temp_vals = [float(r["temperature"]) for r in st_records if r.get("temperature") is not None]
        avg_temp = (sum(temp_vals) / len(temp_vals)) if temp_vals else None
        min_temp = min(temp_vals) if temp_vals else None

        # Determine station resource risk items
        st_risk_score = 0  # 0: LOW, 1: MODERATE, 2: HIGH, 3: CRITICAL

        # 1. Battery Reserve Risk
        if avg_bat is not None and recent_avg_bat is not None:
            if recent_avg_bat < 30.0:
                st_risk_score = max(st_risk_score, 2)
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Battery Reserve",
                        risk_level="HIGH" if recent_avg_bat >= 20.0 else "CRITICAL",
                        main_driver="Battery storage level critically low vs historical baseline",
                        current_value=f"{round(recent_avg_bat, 1)}%",
                        historical_average=f"{round(avg_bat, 1)}%",
                        evidence_text=f"Recent battery SOC {round(recent_avg_bat, 1)}% is below historical operating average {round(avg_bat, 1)}%."
                    )
                )
            elif recent_avg_bat < 45.0 or (avg_bat - recent_avg_bat > 10.0):
                st_risk_score = max(st_risk_score, 1)
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Battery Reserve",
                        risk_level="MODERATE",
                        main_driver="Battery storage experiencing downward draw trend",
                        current_value=f"{round(recent_avg_bat, 1)}%",
                        historical_average=f"{round(avg_bat, 1)}%",
                        evidence_text=f"Recent average SOC {round(recent_avg_bat, 1)}% is depleted relative to baseline {round(avg_bat, 1)}%."
                    )
                )
            else:
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Battery Reserve",
                        risk_level="LOW",
                        main_driver="Battery storage healthy within normal operating bounds",
                        current_value=f"{round(recent_avg_bat, 1)}%",
                        historical_average=f"{round(avg_bat, 1)}%",
                        evidence_text=f"Current reserve {round(recent_avg_bat, 1)}% is stable."
                    )
                )

        # 2. Energy Shortage / High Demand Risk
        if avg_energy > 0:
            if recent_avg_energy > avg_energy * 1.25:
                st_risk_score = max(st_risk_score, 2)
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Energy Demand",
                        risk_level="HIGH",
                        main_driver="Energy consumption surge > 25% above baseline",
                        current_value=f"{round(recent_avg_energy, 1)} kW",
                        historical_average=f"{round(avg_energy, 1)} kW",
                        evidence_text=f"Recent demand {round(recent_avg_energy, 1)} kW represents a +{round(((recent_avg_energy - avg_energy)/avg_energy)*100, 1)}% increase over baseline."
                    )
                )
            elif recent_avg_energy > avg_energy * 1.10:
                st_risk_score = max(st_risk_score, 1)
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Energy Demand",
                        risk_level="MODERATE",
                        main_driver="Elevated energy consumption above seasonal baseline",
                        current_value=f"{round(recent_avg_energy, 1)} kW",
                        historical_average=f"{round(avg_energy, 1)} kW",
                        evidence_text=f"Recent demand {round(recent_avg_energy, 1)} kW is elevated compared to historical {round(avg_energy, 1)} kW."
                    )
                )
            else:
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Energy Demand",
                        risk_level="LOW",
                        main_driver="Consumption matches historical baseline",
                        current_value=f"{round(recent_avg_energy, 1)} kW",
                        historical_average=f"{round(avg_energy, 1)} kW",
                        evidence_text="Station consumption is operating within standard parameters."
                    )
                )

        # 3. Environmental Stress
        if min_temp is not None and avg_temp is not None:
            if min_temp < -35.0:
                st_risk_score = max(st_risk_score, 2)
                station_risks.append(
                    StationResourceRiskItem(
                        station=st,
                        resource="Environmental Stress",
                        risk_level="HIGH",
                        main_driver="Extreme sub-zero cold excursion driving heating loads",
                        current_value=f"{round(min_temp, 1)}°C",
                        historical_average=f"{round(avg_temp, 1)}°C",
                        evidence_text=f"Extreme low temperature of {round(min_temp, 1)}°C observed (mean {round(avg_temp, 1)}°C)."
                    )
                )

        # Categorize overall station risk
        if st_risk_score >= 2:
            st_overall = "HIGH"
            high_risk_stations += 1
        elif st_risk_score == 1:
            st_overall = "MODERATE"
            moderate_risk_stations += 1
        else:
            st_overall = "LOW"
            low_risk_stations += 1

        comparison_chart.append({
            "station": st,
            "overall_risk": st_overall,
            "risk_score": st_risk_score,
            "avg_energy_kw": round(avg_energy, 1),
            "recent_energy_kw": round(recent_avg_energy, 1),
            "avg_battery_soc": round(avg_bat, 1) if avg_bat is not None else None,
            "recent_battery_soc": round(recent_avg_bat, 1) if recent_avg_bat is not None else None,
            "avg_temperature_c": round(avg_temp, 1) if avg_temp is not None else None
        })

    # Overall network risk
    if high_risk_stations > 0:
        network_risk = "HIGH"
    elif moderate_risk_stations > 0:
        network_risk = "MODERATE"
    else:
        network_risk = "LOW"

    return StationResourceRiskAnalytics(
        has_data=True,
        stations_analyzed=len(stations),
        high_risk_stations_count=high_risk_stations,
        moderate_risk_stations_count=moderate_risk_stations,
        low_risk_stations_count=low_risk_stations,
        overall_network_risk=network_risk,
        station_risks=station_risks,
        station_risk_comparison=comparison_chart,
        battery_available=has_battery,
        renewable_available=has_renewable,
        missing_fields_notice=missing_notices
    )
