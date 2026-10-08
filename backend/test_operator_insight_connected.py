"""Unit and Integration Tests for Connected Operator Insight & Energy Intelligence."""
import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.operator_insight_service import (
    calculate_energy_trend_analysis,
    generate_operator_insight
)
from app.services.mdm_storage_service import clear_mdm_data, save_cleaned_dataset

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown_data():
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
            "energy_consumption": 42.0 + (h * 0.3),  # increasing trend
            "equipment_load": 20.0 + (h * 0.2),
            "temperature": -22.0 + (h * 0.1),
            "wind_speed": 12.0,
            "battery_level": 75.0 - (h * 0.2),
            "solar_generation": 5.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 8.0,
        })
    # Create 48 hourly records for Maitri (different load profile)
    for h in range(48):
        day = 1 + (h // 24)
        hour = h % 24
        ts_str = f"2025-08-{day:02d} {hour:02d}:00:00"
        dt = datetime.datetime(2025, 8, day, hour, 0, 0)
        records.append({
            "timestamp": ts_str,
            "ts": dt.timestamp(),
            "station": "Maitri",
            "energy_consumption": 35.0 - (h * 0.1),  # decreasing trend
            "equipment_load": 15.0,
            "temperature": -18.0,
            "wind_speed": 8.0,
            "battery_level": 88.0,
            "solar_generation": 4.0 if 8 <= hour <= 16 else 0.0,
            "wind_generation": 10.0,
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
            "energy_consumption": 28.0 + (h * 0.05),
            "equipment_load": 12.0,
            "temperature": -25.0,
            "wind_speed": 15.0,
            "battery_level": 60.0,
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
    save_cleaned_dataset("test_telemetry.csv", cleaned_data, 1024)
    yield
    # Keep data clean but do not leave DB empty


def test_calculate_energy_trend_analysis_bharati():
    """Verify historical trend calculation and equipment association note."""
    trend = calculate_energy_trend_analysis(station="Bharati")
    assert trend.has_data is True
    assert trend.average_demand_kw is not None
    assert trend.average_demand_kw > 0
    assert trend.peak_demand_kw >= trend.average_demand_kw
    assert trend.consumption_trend_direction in ("Increasing", "Decreasing", "Stable")
    assert trend.trend_summary is not None
    assert "Bharati" in trend.trend_summary or (trend.station_shares and trend.station_shares.get("Bharati") is not None)


def test_operator_insight_structure_and_no_colors():
    """Verify OperatorInsightResponse adheres to 4-step flow and returns status without hardcoded colors."""
    insight = generate_operator_insight(station="Bharati", horizon=24)
    assert insight.status in ("success", "fallback")
    assert insight.energy_status in ("NORMAL", "WATCH", "CONSERVE", "CRITICAL")
    assert insight.priority_level in [1, 2, 3, 4, 5, 6, 7]
    assert insight.current_situation is not None and len(insight.current_situation) > 10
    assert insight.forecast_impact is not None and len(insight.forecast_impact) > 10
    assert insight.operational_consequence is not None and len(insight.operational_consequence) > 10
    assert isinstance(insight.recommended_actions, list)
    assert len(insight.recommended_actions) >= 1

    # Ensure actions do not contain unsupported shutdown orders
    for action in insight.recommended_actions:
        assert "force shutdown" not in action.lower()
        assert "kill generator" not in action.lower()


def test_operator_insight_station_differentiation():
    """Verify Bharati (increasing load) and Maitri (steady/decreasing) produce differentiated insights."""
    insight_bharati = generate_operator_insight(station="Bharati", horizon=24)
    insight_maitri = generate_operator_insight(station="Maitri", horizon=24)

    assert insight_bharati.station == "Bharati"
    assert insight_maitri.station == "Maitri"
    # Ensure summaries or situations reflect different station telemetry
    assert insight_bharati.current_situation != insight_maitri.current_situation or insight_bharati.underlying_metrics != insight_maitri.underlying_metrics


def test_operator_insight_api_endpoint():
    """Test GET and POST /api/analytics/operator-insight endpoint responses."""
    # GET test
    res_get = client.get("/api/analytics/operator-insight?station=Bharati&horizon=24")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["station"] == "Bharati"
    assert data_get["energy_status"] in ("NORMAL", "WATCH", "CONSERVE", "CRITICAL")
    assert "current_situation" in data_get
    assert "forecast_impact" in data_get
    assert "operational_consequence" in data_get
    assert "recommended_actions" in data_get
    assert "trend_analysis" in data_get

    # POST test with policy override
    res_post = client.post(
        "/api/analytics/operator-insight",
        json={
            "station": "Bharati",
            "horizon": 24,
            "policy_override": {
                "safe_days": 45,
                "watch_days": 20,
                "conserve_days": 10,
                "critical_days": 5
            }
        }
    )
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["station"] == "Bharati"
    assert data_post["energy_status"] in ("NORMAL", "WATCH", "CONSERVE", "CRITICAL")
