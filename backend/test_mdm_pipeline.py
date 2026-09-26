"""Unit and integration test suite for Polar-EMS MDM Analytics pipeline."""
import io
from fastapi.testclient import TestClient

from app.main import app
from app.services.schema_mapping_service import map_columns
from app.services.data_cleaning_service import clean_csv_content
from app.services.mdm_storage_service import (
    clear_mdm_data,
    get_mdm_status,
    save_cleaned_dataset,
    query_mdm_records
)
from app.services.energy_analysis_service import calculate_energy_analytics
from app.services.equipment_health_service import calculate_equipment_health_analytics
from app.services.resource_risk_service import calculate_station_resource_risk
from app.services.ai_analysis_service import AIAnalysisService


client = TestClient(app)


def test_schema_mapping_and_financial_isolation():
    headers = [
        "Time", "Station_ID", "Temperature_C", "Solar_Generation_kW",
        "Battery_SOC", "Energy_Consumption_kWh", "Equipment_Load_kW",
        "Wind_Speed_ms", "Price_USD", "Revenue", "Operator_Name", "Transaction_ID"
    ]
    mapped, ignored, classification = map_columns(headers)
    
    assert mapped["Time"] == "timestamp"
    assert mapped["Station_ID"] == "station"
    assert mapped["Temperature_C"] == "temperature"
    assert mapped["Solar_Generation_kW"] == "solar_generation"
    assert mapped["Battery_SOC"] == "battery_level"
    assert mapped["Energy_Consumption_kWh"] == "energy_consumption"
    assert mapped["Equipment_Load_kW"] == "equipment_load"
    assert mapped["Wind_Speed_ms"] == "wind_speed"
    
    assert "Price_USD" in ignored
    assert "Revenue" in ignored
    assert classification["Price_USD"] == "Ignored / Financial"
    assert classification["Revenue"] == "Ignored / Financial"


def test_data_cleaning_and_deduplication():
    csv_text = """Time,Station_ID,Temperature,Energy_Consumption,Price
2026-09-01 00:00:00,Maitri,-18.5,142.5,45.2
2026-09-01 01:00:00,Maitri,-19.0,148.0,46.0
2026-09-01 01:00:00,Maitri,-19.0,148.0,46.0
2026-09-01 02:00:00,Maitri,,150.2,47.0
invalid_time,Maitri,-20.0,155.0,48.0
"""
    result = clean_csv_content(csv_text)
    assert result["success"] is True
    stats = result["stats"]
    assert stats["rows_detected"] == 5
    assert stats["rows_accepted"] == 3
    assert stats["rows_rejected"] == 1  # invalid_time
    assert stats["duplicates_removed"] == 1  # duplicated 01:00:00


def test_mdm_storage_and_historical_merging():
    clear_mdm_data()
    status = get_mdm_status()
    assert status.has_data is False
    assert status.records_count == 0

    csv_part1 = """timestamp,station,temperature,energy_consumption,battery_level
2026-09-01 00:00:00,Maitri,-15.0,120.0,85.0
2026-09-01 01:00:00,Maitri,-16.0,125.0,82.0
"""
    cleaned1 = clean_csv_content(csv_part1)
    save1 = save_cleaned_dataset("batch1.csv", cleaned1)
    assert save1["rows_accepted"] == 2

    # Upload second batch with one overlapping row and one new historical row
    csv_part2 = """timestamp,station,temperature,energy_consumption,battery_level
2026-09-01 01:00:00,Maitri,-16.0,125.0,82.0
2026-08-31 23:00:00,Maitri,-14.0,115.0,88.0
"""
    cleaned2 = clean_csv_content(csv_part2)
    save2 = save_cleaned_dataset("batch2.csv", cleaned2)
    assert save2["rows_accepted"] == 1  # only the 2026-08-31 row is new

    status2 = get_mdm_status()
    assert status2.has_data is True
    assert status2.records_count == 3
    assert status2.stations == ["Maitri"]


def test_analytics_and_empty_state():
    clear_mdm_data()
    empty_energy = calculate_energy_analytics()
    assert empty_energy.has_data is False

    empty_eq = calculate_equipment_health_analytics()
    assert empty_eq.has_data is False

    empty_res = calculate_station_resource_risk()
    assert empty_res.has_data is False


def test_api_endpoints_workflow():
    clear_mdm_data()

    # Upload test CSV via API
    csv_content = """Date_Time,Site,Ambient_Temp,Power_kW,Battery_Percent,Equipment_kW
2026-09-01 00:00:00,Bharati,-22.0,180.0,65.0,90.0
2026-09-01 01:00:00,Bharati,-23.0,195.0,62.0,95.0
2026-09-01 02:00:00,Bharati,-24.0,210.0,58.0,105.0
2026-09-01 03:00:00,Bharati,-25.0,280.0,50.0,160.0
2026-09-01 04:00:00,Bharati,-26.0,185.0,48.0,92.0
"""
    response = client.post(
        "/api/data/upload",
        files={"file": ("test_station.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["rows_accepted"] == 5
    assert "Bharati" in data["stations_detected"]

    # Test status endpoint
    status_resp = client.get("/api/data/status")
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert st_data["has_data"] is True
    assert st_data["records_count"] == 5

    # Test overview endpoint
    overview_resp = client.get("/api/analytics/overview")
    assert overview_resp.status_code == 200
    ov_data = overview_resp.json()
    assert ov_data["has_data"] is True
    assert ov_data["energy_summary"]["avg_power_kw"] > 0
    assert len(ov_data["ai_management_insights"]) > 0

    # Test energy endpoint
    energy_resp = client.get("/api/analytics/energy?station=Bharati")
    assert energy_resp.status_code == 200
    e_data = energy_resp.json()
    assert e_data["has_data"] is True
    assert e_data["peak_demand_kw"] == 280.0

    # Test equipment endpoint
    eq_resp = client.get("/api/analytics/equipment-health")
    assert eq_resp.status_code == 200
    eq_data = eq_resp.json()
    assert eq_data["has_data"] is True
    assert eq_data["has_true_failure_labels"] is False
    assert "not a trained ML failure prediction model" in eq_data["methodology_note"]

    # Test station resource risk
    res_resp = client.get("/api/analytics/resource-risk")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["has_data"] is True
    assert res_data["stations_analyzed"] == 1

    # Test deterministic aggregation endpoints: Monthly
    agg_m = client.get("/api/data/aggregate?period=monthly&anchor_date=2026-09-01")
    assert agg_m.status_code == 200
    m_data = agg_m.json()
    assert m_data["has_data"] is True
    assert m_data["period"] == "monthly"
    assert m_data["current_total"] == 1050.0  # 180 + 195 + 210 + 280 + 185
    assert len(m_data["points"]) == 30  # September has 30 days
    assert m_data["points"][0]["value"] == 1050.0  # 09-01 daily aggregated total
    assert m_data["points"][0]["record_count"] == 5

    # Test Weekly aggregation
    agg_w = client.get("/api/data/aggregate?period=weekly&anchor_date=2026-09-01")
    assert agg_w.status_code == 200
    w_data = agg_w.json()
    assert w_data["has_data"] is True
    assert w_data["period"] == "weekly"
    assert len(w_data["points"]) == 7
    assert w_data["current_total"] == 1050.0

    # Test Yearly aggregation
    agg_y = client.get("/api/data/aggregate?period=yearly&anchor_date=2026-09-01")
    assert agg_y.status_code == 200
    y_data = agg_y.json()
    assert y_data["has_data"] is True
    assert y_data["period"] == "yearly"
    assert len(y_data["points"]) == 12  # 12 months (Jan-Dec)
    assert y_data["current_total"] == 1050.0
    assert y_data["points"][8]["label"] == "Sep"
    assert y_data["points"][8]["value"] == 1050.0


if __name__ == "__main__":
    print("Running test_schema_mapping_and_financial_isolation...")
    test_schema_mapping_and_financial_isolation()
    print("Running test_data_cleaning_and_deduplication...")
    test_data_cleaning_and_deduplication()
    print("Running test_mdm_storage_and_historical_merging...")
    test_mdm_storage_and_historical_merging()
    print("Running test_analytics_and_empty_state...")
    test_analytics_and_empty_state()
    print("Running test_api_endpoints_workflow...")
    test_api_endpoints_workflow()
    print("ALL TESTS PASSED SUCCESSFULLY!")

