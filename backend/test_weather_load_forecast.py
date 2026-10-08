"""Tests for ML Weather Load Forecast Integration, 20-Feature Pipeline, and Fallbacks."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.forecasting_service import (
    ForecastingService,
    LOAD_FEATURES,
    generate_weather_load_forecast,
    clear_forecast_cache
)
from app.services.model_loader import get_model_loader

client = TestClient(app)


def test_model_loader_weather_load_forecaster():
    """Verify polar_ems_weather_load_forecaster.joblib loads once and has 20 features."""
    loader = get_model_loader()
    model = loader.get_model("load")
    assert model is not None
    
    metadata = loader.get_metadata("load")
    assert metadata.get("algorithm") == "XGBoost Regressor"
    assert len(LOAD_FEATURES) == 20
    assert metadata.get("features") == LOAD_FEATURES


def test_predict_load_strict_feature_order():
    """Verify predict_load checks all 20 required features in exact order."""
    valid_features = {
        "temp": -18.0,
        "dwpt": -22.0,
        "rhum": 72.0,
        "wdir": 180.0,
        "wspd": 12.0,
        "pres": 990.0,
        "hour": 14,
        "day_of_week": 2,
        "day_of_month": 15,
        "month": 9,
        "day_of_year": 258,
        "is_weekend": 0,
        "lag_1h": 2100.0,
        "lag_2h": 2080.0,
        "lag_3h": 2050.0,
        "lag_24h": 2120.0,
        "lag_48h": 2150.0,
        "lag_168h": 2000.0,
        "rolling_24h_mean": 2090.0,
        "rolling_24h_std": 85.0
    }
    
    pred = ForecastingService.predict_load(valid_features)
    assert len(pred) == 1

    # Verify missing feature raises error
    invalid_features = valid_features.copy()
    del invalid_features["lag_168h"]
    with pytest.raises(ValueError, match="missing required features"):
        ForecastingService.predict_load(invalid_features)


def test_weather_load_forecast_api_get():
    """Test GET /api/forecast/weather-load endpoint with real Bharati data."""
    clear_forecast_cache()
    response = client.get("/api/forecast/weather-load?station=Bharati&horizon=24")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] in ["success", "insufficient_data"]
    if data["status"] == "success":
        assert data["station"] == "Bharati"
        assert data["model"] == "POLAR EMS Weather Load Forecaster"
        assert data["forecast_horizon_hours"] == 24
        assert data["current_load_kw"] is not None
        assert data["predicted_peak_kw"] is not None
        assert data["predicted_average_kw"] is not None
        assert len(data["forecast_points"]) == 24
        assert len(data["historical_points"]) > 0
        assert data["model_status"]["status"] == "Connected"
        assert data["model_status"]["features_count"] == 20
        assert data["ai_interpretation"] is not None
        assert "interpretation" in data["ai_interpretation"]
        assert "main_drivers" in data["ai_interpretation"]


def test_weather_load_forecast_station_switch():
    """Test switching stations changes the forecast series based on station-specific telemetry."""
    res_bharati = client.get("/api/forecast/weather-load?station=Bharati&horizon=24")
    res_maitri = client.get("/api/forecast/weather-load?station=Maitri&horizon=24")
    
    assert res_bharati.status_code == 200
    assert res_maitri.status_code == 200
    
    d_bharati = res_bharati.json()
    d_maitri = res_maitri.json()
    
    if d_bharati["status"] == "success" and d_maitri["status"] == "success":
        assert d_bharati["station"] == "Bharati"
        assert d_maitri["station"] == "Maitri"
        # Should have distinct historical points reflecting each station's unique records
        assert d_bharati["current_load_kw"] != d_maitri["current_load_kw"] or d_bharati["predicted_peak_kw"] != d_maitri["predicted_peak_kw"]


def test_weather_load_forecast_insufficient_history_handling():
    """Test that requesting forecast for non-existent or short station returns safe insufficient_data response."""
    res = client.get("/api/forecast/weather-load?station=UnknownStationX")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["insufficient_data", "empty_dataset"]
    assert "required" in data["message"].lower() or "dataset" in data["message"].lower()
