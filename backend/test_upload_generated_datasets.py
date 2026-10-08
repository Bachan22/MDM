"""Integration test verifying ingestion and analytics population for generated capstone Excel datasets."""
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.mdm_storage_service import clear_mdm_data, get_mdm_status

client = TestClient(app)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def test_master_dataset_upload_and_full_pipeline_population():
    clear_mdm_data()
    master_file = os.path.join(DATA_DIR, "09_COMPLETE_DEMO_MASTER.xlsx")
    assert os.path.exists(master_file), f"Master dataset not found at {master_file}"

    with open(master_file, "rb") as f:
        resp = client.post(
            "/api/data/upload",
            files={"file": ("09_COMPLETE_DEMO_MASTER.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
    assert resp.status_code == 200
    upload_res = resp.json()
    assert upload_res["success"] is True
    assert upload_res["rows_accepted"] > 0
    assert len(upload_res["stations_detected"]) >= 3
    print(f"[PASS] Master dataset ingested: {upload_res['rows_accepted']} rows across {upload_res['stations_detected']}.")

    # Verify status
    status = get_mdm_status()
    assert status.has_data is True
    assert status.records_count == upload_res["rows_accepted"]
    assert status.stations_count >= 3
    assert status.data_quality_pct >= 95.0
    print("[PASS] Dataset status updated with data quality stats.")

    # Verify Overview Analytics
    ov_resp = client.get("/api/analytics/overview")
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()
    assert ov_data["has_data"] is True
    assert ov_data["energy_summary"]["total_energy"] is not None
    assert ov_data["equipment_summary"]["records_analyzed"] > 0
    assert ov_data["resource_risk_summary"]["stations_analyzed"] >= 3
    assert "dynamic_ai_insights" in ov_data
    print("[PASS] Overview Analytics fully populated from master dataset.")

    # Verify Energy Analytics
    energy_resp = client.get("/api/analytics/energy")
    assert energy_resp.status_code == 200
    energy_data = energy_resp.json()
    assert energy_data["has_data"] is True
    assert energy_data["total_energy_kwh"] > 0
    assert len(energy_data["consumption_by_station"]) >= 3
    print("[PASS] Energy Analytics fully populated.")

    # Verify Equipment Health
    eq_resp = client.get("/api/analytics/equipment-health")
    assert eq_resp.status_code == 200
    eq_data = eq_resp.json()
    assert eq_data["has_data"] is True
    assert eq_data["records_analyzed"] > 0
    assert len(eq_data["equipment_records"]) > 0
    print("[PASS] Equipment Health fully populated.")

    # Verify Resource Risk
    rr_resp = client.get("/api/analytics/resource-risk")
    assert rr_resp.status_code == 200
    rr_data = rr_resp.json()
    assert rr_data["has_data"] is True
    assert rr_data["stations_analyzed"] >= 3
    assert len(rr_data["station_risks"]) >= 3
    print("[PASS] Resource Risk fully populated.")
