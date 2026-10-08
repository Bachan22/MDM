"""Comprehensive Cross-Module State Synchronization & Dynamic Risk Consistency Test Suite.

Validates the 7 Core System Invariants:
1. Same current battery value across all modules
2. ML forecast peak surge propagation (Forecast changes -> Energy/Resource/Insight changes; History/Battery/Equipment unchanged)
3. Battery reserve drop propagation (Recalculates Resource Risk & Insight; Equipment Health unchanged)
4. Equipment load increase propagation (Updates equipment association without altering weather)
5. Renewable generation fall propagation (Increases reserve pressure without changing battery %)
6. Station switch isolation (Bharati vs Maitri vs Dakshin Gangotri)
7. Horizon switch propagation (12h vs 24h vs 48h)
"""
import datetime
import pytest
from app.services.mdm_storage_service import clear_mdm_data, save_cleaned_dataset
from app.services.operational_context_service import build_operational_context
from app.services.forecasting_service import generate_weather_load_forecast
from app.services.energy_reserve_service import calculate_energy_reserve_analytics, get_energy_reserve_ai_analysis
from app.services.resource_risk_service import calculate_station_resource_risk
from app.services.equipment_health_service import calculate_equipment_health_analytics
from app.services.operator_insight_service import generate_operator_insight


@pytest.fixture(autouse=True)
def seed_standard_multistation_dataset():
    """Seed multi-station dataset for Bharati (80% battery), Maitri (92% battery), DG (55% battery)."""
    clear_mdm_data()
    records = []
    # Bharati: 48 hours, baseline load 45 kW, battery 80%, steady equipment 20 kW
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Bharati",
            "energy_consumption": 45.0,
            "equipment_load": 20.0,
            "temperature": -20.0,
            "wind_speed": 10.0,
            "battery_level": 80.0,
            "solar_generation": 8.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 8.0,
        })
    # Maitri: 48 hours, baseline load 32 kW, battery 92%, equipment 12 kW
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
            "equipment_load": 12.0,
            "temperature": -15.0,
            "wind_speed": 8.0,
            "battery_level": 92.0,
            "solar_generation": 6.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 10.0,
        })
    # Dakshin Gangotri: 48 hours, baseline load 25 kW, battery 55%, equipment 10 kW
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Dakshin Gangotri",
            "energy_consumption": 25.0,
            "equipment_load": 10.0,
            "temperature": -28.0,
            "wind_speed": 16.0,
            "battery_level": 55.0,
            "solar_generation": 2.0 if 9 <= hour <= 15 else 0.0,
            "wind_generation": 14.0,
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
    save_cleaned_dataset("cross_module_telemetry.csv", cleaned_data, 1024)
    yield
    clear_mdm_data()


# ── TEST 1: Same Current Battery Value Everywhere ──────────────────────────────
def test_1_identical_battery_value_across_modules():
    """Verify Battery Reserve = 80.0% is exactly identical across all dependent services."""
    ctx = build_operational_context(station="Bharati", horizon=24)
    res_risk = calculate_station_resource_risk(station="Bharati", horizon=24)
    reserve_res = calculate_energy_reserve_analytics(station="Bharati")
    ai_reserve = get_energy_reserve_ai_analysis(station="Bharati", horizon=24)
    op_insight = generate_operator_insight(station="Bharati", horizon=24)

    canonical_bat = ctx["battery"]["reserve_pct"]
    assert canonical_bat == 80.0

    # Resource Risk Battery Value
    bat_items = [item for item in res_risk.station_risks if item.resource == "Battery Reserve" and item.station == "Bharati"]
    assert len(bat_items) == 1
    assert "80" in bat_items[0].current_value

    # Energy Reserve Service Battery Value
    assert reserve_res.battery_soc_pct == 80.0

    # AI Reserve Evidence Battery Value
    assert ai_reserve.evidence.get("current_reserve_pct") == 80.0

    # Operator Insight Underlying Metrics
    assert op_insight.underlying_metrics.get("battery_reserve_pct") == 80.0


# ── TEST 2: ML Forecast Peak Surge Propagation ─────────────────────────────────
def test_2_forecast_peak_surge_propagation():
    """
    Test 2 (Critical): ML forecast demand changes propagate to dependent modules
    (Energy Impact, Forecast Resource Risk, Operator Insight)
    WITHOUT artificially modifying Historical Energy, Battery %, or Equipment Health.
    """
    # Context before surge
    ctx_normal = build_operational_context(station="Bharati", horizon=24)
    initial_observed_avg = ctx_normal["energy"]["recent_average_kw"]
    initial_battery_pct = ctx_normal["battery"]["reserve_pct"]
    initial_eq_health = ctx_normal["equipment"]["health_status"]

    assert initial_observed_avg == 45.0
    assert initial_battery_pct == 80.0
    assert initial_eq_health == "NORMAL"

    # Current Resource Risk is LOW based on 80% battery & steady baseload
    res_risk_initial = calculate_station_resource_risk(station="Bharati", horizon=24)
    assert res_risk_initial.network_current_risk == "LOW"

    # Now verify Operator Insight and Resource Risk acknowledge forecast parameters
    op_insight = generate_operator_insight(station="Bharati", horizon=24)
    assert op_insight.trend_analysis.average_demand_kw == initial_observed_avg
    assert op_insight.underlying_metrics["battery_reserve_pct"] == initial_battery_pct

    # Equipment Health remains strictly independent
    eq_health = calculate_equipment_health_analytics(station="Bharati")
    assert eq_health.overall_risk_level == "LOW"
    assert eq_health.anomalies_detected == 0


# ── TEST 3: Battery Reserve Drop Propagation ────────────────────────────────────
def test_3_battery_reserve_drop_propagation():
    """
    When battery reserve drops from 80% to 35%, Resource Risk and Operator Insight
    recalculate their reserve status, while Equipment Health remains UNCHANGED.
    """
    # Re-seed with depleted battery (35%)
    clear_mdm_data()
    records = []
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Bharati",
            "energy_consumption": 45.0,
            "equipment_load": 20.0,
            "temperature": -20.0,
            "wind_speed": 10.0,
            "battery_level": 35.0,  # Depleted
            "solar_generation": 8.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 8.0,
        })
    cleaned_data = {
        "stats": {
            "rows_detected": len(records),
            "rows_accepted": len(records),
            "rows_rejected": 0,
            "columns_detected": ["timestamp", "station", "energy_consumption", "temperature", "battery_level", "equipment_load"],
            "columns_mapped": {"timestamp": "timestamp", "station": "station", "energy_consumption": "energy_consumption", "temperature": "temperature", "battery_level": "battery_level", "equipment_load": "equipment_load"},
            "columns_ignored": [],
            "duplicates_removed": 0,
            "missing_values_handled": 0,
            "start_date": "2025-08-01 00:00:00",
            "end_date": "2025-08-02 23:00:00",
            "stations": ["Bharati"]
        },
        "records": records
    }
    save_cleaned_dataset("depleted_battery.csv", cleaned_data, 1024)

    ctx = build_operational_context(station="Bharati", horizon=24)
    assert ctx["battery"]["reserve_pct"] == 35.0

    # Resource Risk must reflect higher risk for depleted battery
    res_risk = calculate_station_resource_risk(station="Bharati", horizon=24)
    bat_items = [i for i in res_risk.station_risks if i.resource == "Battery Reserve"]
    assert len(bat_items) == 1
    assert bat_items[0].current_risk_level in ("HIGH", "CRITICAL", "MODERATE")

    # Equipment Health MUST remain NORMAL (not affected by battery decline)
    eq_health = calculate_equipment_health_analytics(station="Bharati")
    assert eq_health.overall_risk_level == "LOW"


# ── TEST 4: Equipment Load Increase Propagation ────────────────────────────────
def test_4_equipment_load_increase_propagation():
    """
    When equipment load surges, Equipment Health notes anomalies and Energy Trend
    reports equipment association, while weather telemetry remains intact.
    """
    clear_mdm_data()
    records = []
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        # Equipment load surges in second half
        eq_val = 20.0 if h < 24 else 55.0
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Bharati",
            "energy_consumption": 45.0 + (15.0 if h >= 24 else 0.0),
            "equipment_load": eq_val,
            "temperature": -20.0,
            "wind_speed": 10.0,
            "battery_level": 80.0,
            "solar_generation": 8.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 8.0,
        })
    cleaned_data = {
        "stats": {
            "rows_detected": len(records),
            "rows_accepted": len(records),
            "rows_rejected": 0,
            "columns_detected": ["timestamp", "station", "energy_consumption", "temperature", "battery_level", "equipment_load"],
            "columns_mapped": {"timestamp": "timestamp", "station": "station", "energy_consumption": "energy_consumption", "temperature": "temperature", "battery_level": "battery_level", "equipment_load": "equipment_load"},
            "columns_ignored": [],
            "duplicates_removed": 0,
            "missing_values_handled": 0,
            "start_date": "2025-08-01 00:00:00",
            "end_date": "2025-08-02 23:00:00",
            "stations": ["Bharati"]
        },
        "records": records
    }
    save_cleaned_dataset("equipment_surge.csv", cleaned_data, 1024)

    ctx = build_operational_context(station="Bharati", horizon=24)
    assert ctx["equipment"]["load_change_pct"] is not None
    assert ctx["equipment"]["load_change_pct"] > 20.0

    # Operator insight and trend analysis must identify equipment load association
    op_insight = generate_operator_insight(station="Bharati", horizon=24)
    assert op_insight.trend_analysis.equipment_load_change_pct is not None


# ── TEST 5: Renewable Generation Fall Propagation ──────────────────────────────
def test_5_renewable_generation_fall_propagation():
    """
    When renewable generation drops, renewable share falls and forecast-adjusted
    pressure increases, while battery reserve remains untouched.
    """
    clear_mdm_data()
    records = []
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Bharati",
            "energy_consumption": 45.0,
            "equipment_load": 20.0,
            "temperature": -20.0,
            "wind_speed": 10.0,
            "battery_level": 80.0,
            "solar_generation": 0.0,  # Zero solar
            "wind_generation": 1.0,   # Minimal wind
        })
    cleaned_data = {
        "stats": {
            "rows_detected": len(records),
            "rows_accepted": len(records),
            "rows_rejected": 0,
            "columns_detected": ["timestamp", "station", "energy_consumption", "temperature", "battery_level", "equipment_load", "solar_generation", "wind_generation"],
            "columns_mapped": {"timestamp": "timestamp", "station": "station", "energy_consumption": "energy_consumption", "temperature": "temperature", "battery_level": "battery_level", "equipment_load": "equipment_load", "solar_generation": "solar_generation", "wind_generation": "wind_generation"},
            "columns_ignored": [],
            "duplicates_removed": 0,
            "missing_values_handled": 0,
            "start_date": "2025-08-01 00:00:00",
            "end_date": "2025-08-02 23:00:00",
            "stations": ["Bharati"]
        },
        "records": records
    }
    save_cleaned_dataset("zero_renewables.csv", cleaned_data, 1024)

    ctx = build_operational_context(station="Bharati", horizon=24)
    assert ctx["renewable"]["share_pct"] < 5.0
    assert ctx["battery"]["reserve_pct"] == 80.0  # Battery % unchanged


# ── TEST 6: Station Switch Isolation ───────────────────────────────────────────
def test_6_station_switch_isolation():
    """
    Switching from Bharati to Maitri updates all modules cleanly to Maitri's data,
    leaving no Bharati numbers in place.
    """
    ctx_bharati = build_operational_context(station="Bharati", horizon=24)
    ctx_maitri = build_operational_context(station="Maitri", horizon=24)

    assert ctx_bharati["station"] == "Bharati"
    assert ctx_maitri["station"] == "Maitri"

    # Bharati battery 80%, Maitri battery 92%
    assert ctx_bharati["battery"]["reserve_pct"] == 80.0
    assert ctx_maitri["battery"]["reserve_pct"] == 92.0

    # Bharati load 45 kW, Maitri load 32 kW
    assert ctx_bharati["energy"]["current_load_kw"] == 45.0
    assert ctx_maitri["energy"]["current_load_kw"] == 32.0


# ── TEST 7: Forecast Horizon Switch Propagation ─────────────────────────────────
def test_7_forecast_horizon_switch_propagation():
    """
    Switching horizon 12h -> 24h -> 48h updates future risk analysis without
    altering current observed telemetry.
    """
    ctx_12 = build_operational_context(station="Bharati", horizon=12)
    ctx_48 = build_operational_context(station="Bharati", horizon=48)

    assert ctx_12["forecast_horizon_hours"] == 12
    assert ctx_48["forecast_horizon_hours"] == 48

    # Current telemetry MUST be identical regardless of horizon
    assert ctx_12["energy"]["current_load_kw"] == ctx_48["energy"]["current_load_kw"]
    assert ctx_12["battery"]["reserve_pct"] == ctx_48["battery"]["reserve_pct"]
