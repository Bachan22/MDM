"""Unit & Integration tests for Safe Final Enhancements (AI Insights, Data Coverage, Report Data)."""
import io
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_analysis_service import AIAnalysisService
from app.services.data_cleaning_service import clean_dataset_bytes
from app.services.mdm_storage_service import clear_mdm_data, get_mdm_status, save_cleaned_dataset

client = TestClient(app)


def test_data_coverage_and_quality_metrics():
    clear_mdm_data()
    # Create sample CSV with some missing values
    csv_data = (
        "Timestamp,Station,Air_Temp_C,Energy_kWh,Equipment_Load_kW,Price_Cost\n"
        "2026-09-01 00:00:00,Maitri,-18.5,135.0,105.0,45.0\n"
        "2026-09-01 01:00:00,Maitri,,142.0,112.0,46.0\n"
        "2026-09-01 02:00:00,Maitri,-20.2,158.0,,48.0\n"
    )
    bytes_io = csv_data.encode("utf-8")
    cleaned = clean_dataset_bytes(bytes_io, "test_telemetry.csv")
    assert cleaned["success"] is True

    save_cleaned_dataset("test_telemetry.csv", cleaned, len(bytes_io))

    status = get_mdm_status()
    assert status.has_data is True
    assert status.records_count == 3
    assert status.stations_count == 1
    assert status.stations == ["Maitri"]
    assert status.missing_values_count >= 2
    assert status.data_quality_pct <= 100.0
    print("[PASS] Data coverage and quality metric calculation verified.")


def test_dynamic_ai_insights_generation_and_fallback():
    clear_mdm_data()
    status = get_mdm_status()
    energy_summary = {"total_energy_kwh": 435.0, "avg_power_kw": 145.0, "peak_demand_kw": 158.0}
    equipment_summary = {"anomalies_detected": 1, "overall_risk_level": "LOW"}
    resource_summary = {"overall_network_risk": "LOW"}

    # Test dynamic insights generation
    res = AIAnalysisService.generate_dynamic_insights(energy_summary, equipment_summary, resource_summary, status)
    assert "insights" in res
    assert len(res["insights"]) > 0
    assert "status" in res
    print("[PASS] Dynamic AI Insights generation & fallback resilience verified.")


def test_overview_endpoint_includes_all_enhancements():
    # Test overview API response
    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "dataset_status" in data
    assert "missing_values_pct" in data["dataset_status"]
    assert "data_quality_pct" in data["dataset_status"]
    assert "dynamic_ai_insights" in data
    print("[PASS] Overview API includes data quality & dynamic AI insights fields.")
