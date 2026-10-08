"""Verification test suite for Dynamic AI Energy Reserve & Operational Recommendation."""
import datetime
import pytest
from app.services.energy_reserve_service import (
    build_energy_reserve_ai_context,
    get_energy_reserve_ai_analysis,
)
from app.schemas.mdm_models import EnergyReserveAIResponse
from app.services.mdm_storage_service import clear_mdm_data, save_cleaned_dataset


@pytest.fixture(autouse=True)
def ensure_telemetry_data():
    """Seed test telemetry dataset for Bharati, Maitri, and Dakshin Gangotri stations."""
    clear_mdm_data()
    records = []
    # Create 48 hourly records for Bharati
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Bharati",
            "energy_consumption": 45.0 + (h * 0.2),
            "equipment_load": 22.0 + (h * 0.1),
            "temperature": -20.0,
            "wind_speed": 11.0,
            "battery_level": 80.0,
            "solar_generation": 6.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 9.0,
        })
    # Create 48 hourly records for Maitri
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Maitri",
            "energy_consumption": 32.0,
            "equipment_load": 14.0,
            "temperature": -15.0,
            "wind_speed": 7.0,
            "battery_level": 92.0,
            "solar_generation": 4.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 11.0,
        })
    # Create 48 hourly records for Dakshin Gangotri
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Dakshin Gangotri",
            "energy_consumption": 26.0,
            "equipment_load": 10.0,
            "temperature": -28.0,
            "wind_speed": 16.0,
            "battery_level": 55.0,
            "solar_generation": 1.0 if 9 <= hour <= 15 else 0.0,
            "wind_generation": 15.0,
        })

    cleaned_data = {
        "stats": {
            "rows_detected": len(records),
            "rows_accepted": len(records),
            "rows_rejected": 0,
            "columns_detected": ["timestamp", "station", "energy_consumption", "temperature", "battery_level", "equipment_load", "solar_generation", "wind_generation", "wind_speed"],
            "columns_mapped": {
                "timestamp": "timestamp",
                "station": "station",
                "energy_consumption": "energy_consumption",
                "temperature": "temperature",
                "battery_level": "battery_level",
                "equipment_load": "equipment_load",
                "solar_generation": "solar_generation",
                "wind_generation": "wind_generation",
                "wind_speed": "wind_speed"
            },
            "columns_ignored": [],
            "duplicates_removed": 0,
            "missing_values_handled": 0,
            "start_date": "2025-08-01 00:00:00",
            "end_date": "2025-08-02 23:00:00",
            "stations": ["Bharati", "Maitri", "Dakshin Gangotri"]
        },
        "records": records
    }
    save_cleaned_dataset("test_telemetry.csv", cleaned_data, 1024)
    yield


def test_build_energy_reserve_ai_context_bharati():
    ctx = build_energy_reserve_ai_context(station="Bharati", horizon=24)
    assert ctx["has_data"] is True
    assert ctx["station"] == "Bharati"
    assert ctx["forecast_horizon_hours"] == 24
    assert "current_energy" in ctx
    assert "forecast" in ctx
    assert "renewable" in ctx
    assert "battery" in ctx
    assert "risk" in ctx
    assert ctx["risk"]["energy_status"] in ("NORMAL", "WATCH", "CONSERVE", "CRITICAL")
    assert "deterministic_actions" in ctx
    assert len(ctx["deterministic_actions"]) > 0


def test_build_energy_reserve_ai_context_horizons():
    ctx12 = build_energy_reserve_ai_context(station="Maitri", horizon=12)
    ctx48 = build_energy_reserve_ai_context(station="Maitri", horizon=48)
    assert ctx12["forecast_horizon_hours"] == 12
    assert ctx48["forecast_horizon_hours"] == 48


def test_get_energy_reserve_ai_analysis_bharati():
    res = get_energy_reserve_ai_analysis(station="Bharati", horizon=24)
    assert isinstance(res, EnergyReserveAIResponse)
    assert res.station == "Bharati"
    assert res.forecast_horizon_hours == 24
    assert res.energy_status in ("NORMAL", "WATCH", "CONSERVE", "CRITICAL")
    assert len(res.energy_situation) > 0
    assert len(res.forecast_impact) > 0
    assert len(res.reserve_recommendation) > 0
    assert len(res.recommended_actions) > 0
    assert len(res.why) > 0
    assert "forecast_peak_kw" in res.evidence
    assert res.evidence["forecast_peak_kw"] is not None
    assert "solar" in res.signal_availability
    assert "wind" in res.signal_availability
    assert res.signal_availability["solar"] in ("Observed", "Forecasted", "Unavailable")


def test_station_switching_differentiation():
    res_bharati = get_energy_reserve_ai_analysis(station="Bharati", horizon=24)
    res_maitri = get_energy_reserve_ai_analysis(station="Maitri", horizon=24)
    res_dg = get_energy_reserve_ai_analysis(station="Dakshin Gangotri", horizon=24)

    assert res_bharati.station == "Bharati"
    assert res_maitri.station == "Maitri"
    assert res_dg.station == "Dakshin Gangotri"

    # Verify each station has its own real telemetry numbers
    assert res_bharati.evidence["current_load_kw"] != res_maitri.evidence["current_load_kw"] or \
           res_bharati.evidence["forecast_peak_kw"] != res_maitri.evidence["forecast_peak_kw"]
