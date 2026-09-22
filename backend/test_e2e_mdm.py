"""End-to-end verification test for Polar-EMS MDM system."""
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_e2e_test():
    print("=== Step 1: Verify Initial Clean State ===")
    clear_resp = client.delete("/api/data/clear")
    assert clear_resp.status_code == 200

    status = client.get("/api/data/status").json()
    assert status["has_data"] is False
    assert status["records_count"] == 0

    overview = client.get("/api/analytics/overview").json()
    assert overview["has_data"] is False
    print("[PASS] Initial clean state verified (0 fake values).")

    print("\n=== Step 2: Upload Dataset A (Sept 2026 with Financial Columns) ===")
    dataset_a = """Time,Station_ID,Temperature_C,Power_kW,Battery_SOC,Equipment_Load_kW,Wind_Speed_ms,Price_USD,Revenue,Operator_Name
2026-09-01 00:00:00,Maitri,-18.2,140.5,82.0,110.0,7.5,45.20,1200,John
2026-09-01 01:00:00,Maitri,-19.0,145.0,80.0,115.0,8.0,46.00,1250,John
2026-09-01 02:00:00,Maitri,-20.5,152.0,78.0,120.0,9.2,46.50,1300,John
2026-09-01 03:00:00,Maitri,-22.0,175.0,72.0,140.0,11.5,48.00,1450,John
2026-09-01 04:00:00,Maitri,-24.0,210.0,65.0,185.0,14.0,52.00,1800,John
2026-09-01 00:00:00,Bharati,-15.0,110.0,90.0,85.0,5.0,42.00,900,Alice
2026-09-01 01:00:00,Bharati,-15.5,112.0,88.0,86.0,5.2,42.50,910,Alice
2026-09-01 02:00:00,Bharati,-16.0,115.0,86.0,88.0,5.5,43.00,930,Alice
"""
    up_resp = client.post(
        "/api/data/upload",
        files={"file": ("sept_2026_dataset.csv", io.BytesIO(dataset_a.encode("utf-8")), "text/csv")}
    )
    assert up_resp.status_code == 200
    up_data = up_resp.json()
    assert up_data["success"] is True
    assert up_data["rows_accepted"] == 8
    assert "Price_USD" in up_data["columns_ignored"]
    assert "Revenue" in up_data["columns_ignored"]
    assert "Maitri" in up_data["stations_detected"]
    assert "Bharati" in up_data["stations_detected"]
    print(f"[PASS] Dataset A uploaded: {up_data['rows_accepted']} rows accepted, financial fields safely ignored.")

    print("\n=== Step 3: Verify Analytics on Dataset A ===")
    status_a = client.get("/api/data/status").json()
    assert status_a["has_data"] is True
    assert status_a["records_count"] == 8
    assert status_a["stations_count"] == 2

    # Energy Analysis
    energy = client.get("/api/analytics/energy").json()
    assert energy["has_data"] is True
    assert energy["peak_demand_kw"] == 210.0
    assert "Maitri" in energy["consumption_by_station"]
    assert "Bharati" in energy["consumption_by_station"]
    print(f"[PASS] Energy Analytics: Peak = {energy['peak_demand_kw']} kW, Total = {energy['total_energy_kwh']} {energy['total_energy_unit']}.")

    # Station Filter
    energy_maitri = client.get("/api/analytics/energy?station=Maitri").json()
    assert energy_maitri["has_data"] is True
    assert energy_maitri["peak_demand_kw"] == 210.0
    assert len(energy_maitri["consumption_by_station"]) == 1
    print("[PASS] Station filtering verified.")

    # Equipment Health
    eq = client.get("/api/analytics/equipment-health").json()
    assert eq["has_data"] is True
    assert eq["records_analyzed"] == 8
    assert eq["has_true_failure_labels"] is False
    assert "not a trained ML failure prediction model" in eq["methodology_note"]
    print("[PASS] Equipment Health: Methodology disclaimer present, statistical anomalies analyzed.")

    # Resource Risk
    rr = client.get("/api/analytics/resource-risk").json()
    assert rr["has_data"] is True
    assert rr["stations_analyzed"] == 2
    assert len(rr["station_risks"]) > 0
    print("[PASS] Station Resource Risk: Evaluated 2 stations with evidence strings.")

    print("\n=== Step 4: Upload Dataset B (Historical 2025 Data) & Historical Merging ===")
    dataset_b = """Time,Station_ID,Temperature_C,Power_kW,Battery_SOC,Equipment_Load_kW,Wind_Speed_ms
2025-01-01 00:00:00,Maitri,-10.0,95.0,95.0,75.0,4.0
2025-01-01 01:00:00,Maitri,-10.5,98.0,94.0,76.0,4.2
2025-01-01 02:00:00,Maitri,-11.0,100.0,92.0,78.0,4.5
2026-09-01 04:00:00,Maitri,-24.0,210.0,65.0,185.0,14.0
"""
    up_b_resp = client.post(
        "/api/data/upload",
        files={"file": ("hist_2025_dataset.csv", io.BytesIO(dataset_b.encode("utf-8")), "text/csv")}
    )
    assert up_b_resp.status_code == 200
    up_b_data = up_b_resp.json()
    # 4 rows in CSV, 1 is duplicate of 2026-09-01 04:00:00 -> 3 new rows added
    assert up_b_data["rows_accepted"] == 3
    assert up_b_data["duplicates_removed"] >= 1
    print(f"[PASS] Historical Dataset B merged: Added 3 new records, skipped 1 duplicate timestamp.")

    status_merged = client.get("/api/data/status").json()
    assert status_merged["records_count"] == 11
    assert "2025-01-01" in status_merged["date_range_start"]
    assert "2026-09-01" in status_merged["date_range_end"]
    print(f"[PASS] Unified Historical Timeline: {status_merged['date_range_start']} -> {status_merged['date_range_end']}.")

    print("\n=== Step 5: Duplicate Upload Test ===")
    up_dup_resp = client.post(
        "/api/data/upload",
        files={"file": ("hist_2025_dataset.csv", io.BytesIO(dataset_b.encode("utf-8")), "text/csv")}
    )
    assert up_dup_resp.status_code == 200
    up_dup_data = up_dup_resp.json()
    assert up_dup_data["rows_accepted"] == 0
    assert up_dup_data["duplicates_removed"] >= 4

    status_after_dup = client.get("/api/data/status").json()
    assert status_after_dup["records_count"] == 11  # No double counting!
    print("[PASS] Deduplication verified: Re-uploading identical file added 0 records (no double counting).")

    print("\n=== Step 6: Verify Overview Management Insights with AI Layer ===")
    overview = client.get("/api/analytics/overview").json()
    assert overview["has_data"] is True
    assert len(overview["ai_management_insights"]) >= 2
    for ins in overview["ai_management_insights"]:
        assert "finding" in ins and len(ins["finding"]) > 0
        assert "evidence" in ins and len(ins["evidence"]) > 0
        assert "recommendation" in ins and len(ins["recommendation"]) > 0
    print("[PASS] AI Management Insights verified with structured findings, drivers and evidence.")

    print("\n=== ALL E2E ACCEPTANCE TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_e2e_test()
