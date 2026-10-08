"""Energy consumption statistical analysis service for Polar-EMS MDM."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..schemas.mdm_models import EnergyAnalytics
from .mdm_storage_service import query_mdm_records, get_data_version

_ENERGY_CACHE: Dict[str, EnergyAnalytics] = {}


def clear_energy_cache() -> None:
    _ENERGY_CACHE.clear()


def calculate_energy_analytics(
    station: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> EnergyAnalytics:
    """Calculates deterministic energy consumption analytics from real uploaded data."""
    version = get_data_version()
    cache_key = f"{version}_{station}_{start_date}_{end_date}"
    if cache_key in _ENERGY_CACHE:
        return _ENERGY_CACHE[cache_key]

    records = query_mdm_records(station=station, start_date=start_date, end_date=end_date)

    if not records:
        res = EnergyAnalytics(
            has_data=False,
            data_period={"start": start_date, "end": end_date},
            missing_fields_notice=["No records found matching the specified filters or no dataset uploaded."]
        )
        _ENERGY_CACHE[cache_key] = res
        return res

    # Filter records with energy_consumption or equipment_load fallback
    for r in records:
        if r.get("energy_consumption") is None and r.get("equipment_load") is not None:
            r["energy_consumption"] = r["equipment_load"]

    energy_records = [r for r in records if r.get("energy_consumption") is not None]
    if not energy_records:
        return EnergyAnalytics(
            has_data=False,
            data_period={"start": records[0]["timestamp"], "end": records[-1]["timestamp"]},
            missing_fields_notice=["Uploaded dataset does not contain an identifiable 'energy_consumption' or 'power' column."]
        )

    consumptions = [float(r["energy_consumption"]) for r in energy_records]
    total_energy_kwh = sum(consumptions)
    avg_power_kw = total_energy_kwh / len(consumptions)
    peak_demand_kw = max(consumptions)
    min_demand_kw = min(consumptions)

    # Equipment load if present
    load_vals = [float(r["equipment_load"]) for r in records if r.get("equipment_load") is not None]
    avg_equipment_load_kw = (sum(load_vals) / len(load_vals)) if load_vals else None

    # Trend calculation (comparing first half vs second half)
    half = len(consumptions) // 2
    trend_direction = "Stable"
    trend_pct = 0.0
    if half > 0:
        first_half_avg = sum(consumptions[:half]) / half
        second_half_avg = sum(consumptions[half:]) / len(consumptions[half:])
        if first_half_avg > 0:
            diff = second_half_avg - first_half_avg
            trend_pct = round((diff / first_half_avg) * 100.0, 1)
            if trend_pct > 2.0:
                trend_direction = "Increasing"
            elif trend_pct < -2.0:
                trend_direction = "Decreasing"

    # Consumption by station
    consumption_by_station: Dict[str, float] = {}
    for r in energy_records:
        st = r["station"]
        val = float(r["energy_consumption"])
        consumption_by_station[st] = round(consumption_by_station.get(st, 0.0) + val, 2)

    # Downsampled time series for charts (max 150 points)
    step = max(1, len(energy_records) // 120)
    sampled_records = energy_records[::step]
    time_series = [
        {
            "timestamp": r["timestamp"],
            "energy_kwh": round(float(r["energy_consumption"]), 2),
            "station": r["station"],
            "temperature_c": round(float(r["temperature"]), 1) if r.get("temperature") is not None else None,
            "equipment_load_kw": round(float(r["equipment_load"]), 2) if r.get("equipment_load") is not None else None
        }
        for r in sampled_records
    ]

    # Temp vs Energy correlation points
    temp_records = [r for r in energy_records if r.get("temperature") is not None]
    temp_step = max(1, len(temp_records) // 80)
    temp_vs_energy = [
        {
            "temperature_c": round(float(r["temperature"]), 1),
            "energy_kwh": round(float(r["energy_consumption"]), 2),
            "station": r["station"]
        }
        for r in temp_records[::temp_step]
    ]

    # Load vs Energy points
    load_records = [r for r in energy_records if r.get("equipment_load") is not None]
    load_step = max(1, len(load_records) // 80)
    load_vs_energy = [
        {
            "equipment_load_kw": round(float(r["equipment_load"]), 2),
            "energy_kwh": round(float(r["energy_consumption"]), 2),
            "station": r["station"]
        }
        for r in load_records[::load_step]
    ]

    # Renewable vs Consumption check
    has_solar = any(r.get("solar_generation") is not None for r in records)
    has_wind = any(r.get("wind_generation") is not None or r.get("wind_speed") is not None for r in records)
    renewable_available = has_solar or has_wind

    renewable_vs_consumption = None
    missing_notices = []

    if renewable_available:
        renewable_vs_consumption = []
        for r in sampled_records:
            solar = float(r.get("solar_generation") or 0.0)
            wind = float(r.get("wind_generation") or 0.0)
            # Estimate wind generation from wind speed if only speed is given (150kW rated at 12m/s)
            if wind == 0.0 and r.get("wind_speed") is not None:
                ws = float(r["wind_speed"])
                wind = min(150.0, max(0.0, (ws / 12.0) ** 3 * 150.0))
            tot_renewable = solar + wind
            renewable_vs_consumption.append({
                "timestamp": r["timestamp"],
                "consumption_kwh": round(float(r["energy_consumption"]), 2),
                "renewable_kwh": round(tot_renewable, 2),
                "solar_kwh": round(solar, 2),
                "wind_kwh": round(wind, 2)
            })
    else:
        missing_notices.append("Solar and wind generation data unavailable in uploaded dataset.")

    if not temp_records:
        missing_notices.append("Temperature data unavailable.")
    if not load_records:
        missing_notices.append("Equipment load data unavailable.")

    # Unit scaling (if total > 10,000 kWh, provide MWh helper)
    unit = "kWh"
    display_total = round(total_energy_kwh, 2)
    if total_energy_kwh > 50000.0:
        unit = "MWh"
        display_total = round(total_energy_kwh / 1000.0, 2)

    res = EnergyAnalytics(
        has_data=True,
        data_period={
            "start": records[0]["timestamp"],
            "end": records[-1]["timestamp"]
        },
        total_energy_kwh=display_total,
        total_energy_unit=unit,
        avg_power_kw=round(avg_power_kw, 2),
        peak_demand_kw=round(peak_demand_kw, 2),
        min_demand_kw=round(min_demand_kw, 2),
        avg_equipment_load_kw=round(avg_equipment_load_kw, 2) if avg_equipment_load_kw is not None else None,
        trend_direction=trend_direction,
        trend_pct=trend_pct,
        consumption_by_station=consumption_by_station,
        time_series=time_series,
        temp_vs_energy=temp_vs_energy,
        load_vs_energy=load_vs_energy,
        renewable_vs_consumption=renewable_vs_consumption,
        renewable_available=renewable_available,
        missing_fields_notice=missing_notices
    )
    _ENERGY_CACHE[cache_key] = res
    return res
