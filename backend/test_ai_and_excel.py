"""Test suite for AI API integration and Excel/CSV dataset pipeline."""
import io
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_analysis_service import AIAnalysisService
from app.services.data_cleaning_service import clean_dataset_bytes
from app.services.mdm_storage_service import clear_mdm_data, get_mdm_status

client = TestClient(app)


def test_excel_upload_and_cleaning():
    clear_mdm_data()
    # Create an in-memory multi-sheet Excel workbook
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Metadata / notes (less relevant)
        df_notes = pd.DataFrame({"Notes": ["Station telemetry log", "Operator shift B"], "ID": [1, 2]})
        df_notes.to_excel(writer, sheet_name="Overview_Notes", index=False)

        # Sheet 2: Actual Telemetry (Relevant data)
        df_data = pd.DataFrame({
            "Timestamp": ["2026-09-01 00:00:00", "2026-09-01 01:00:00", "2026-09-01 02:00:00"],
            "Station": ["Maitri", "Maitri", "Maitri"],
            "Air_Temp_C": [-18.5, -19.0, -20.2],
            "Energy_kWh": [135.0, 142.0, 158.0],
            "Battery_SOC": [84.0, 81.0, 77.0],
            "Machine_Load_kW": [105.0, 112.0, 125.0],
            "Wind_Velocity_ms": [8.0, 8.5, 9.1],
            "Tariff_Cost": [45.0, 46.0, 48.0]  # Financial column
        })
        df_data.to_excel(writer, sheet_name="Station_Readings", index=False)

    excel_bytes = output.getvalue()

    # Test clean_dataset_bytes with auto sheet selection
    cleaned = clean_dataset_bytes(excel_bytes, "station_telemetry.xlsx")
    assert cleaned["success"] is True
    assert cleaned["stats"]["selected_sheet"] == "Station_Readings"
    assert cleaned["stats"]["rows_accepted"] == 3
    assert "Tariff_Cost" in cleaned["stats"]["columns_ignored"]
    print("[PASS] Excel workbook auto-sheet selection and data cleaning verified.")

    # Upload via API
    resp = client.post(
        "/api/data/upload",
        files={"file": ("station_telemetry.xlsx", io.BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True
    assert res_data["rows_accepted"] == 3
    assert "Maitri" in res_data["stations_detected"]
    print("[PASS] Excel upload via /api/data/upload succeeded.")


def test_ai_analysis_service_live_api():
    # Test real AI API analysis
    sample_summary = {
        "total_energy_kwh": 435.0,
        "avg_power_kw": 145.0,
        "peak_demand_kw": 158.0,
        "trend_direction": "Increasing",
        "trend_pct": 17.0,
        "station": "Maitri"
    }

    res = AIAnalysisService.analyze_dataset(
        data=sample_summary,
        analysis_type="energy_consumption",
        context={"station": "Maitri", "season": "Antarctic Spring"}
    )
    assert isinstance(res, dict)
    assert "summary" in res
    assert "key_findings" in res
    assert "risk_level" in res
    assert "recommendations" in res
    assert "source" in res
    print(f"[PASS] AI Analysis output ({res['source']}): {res['summary']}")


def test_ai_endpoint_route():
    resp = client.post("/api/analytics/ai", json={
        "analysis_type": "equipment_health",
        "data": {
            "records_analyzed": 500,
            "anomalies_detected": 4,
            "overall_risk_level": "MODERATE",
            "equipment_records": [
                {"equipment_id": "Generator-01", "main_signal": "Thermal excursions", "anomaly_count": 4}
            ]
        }
    })
    assert resp.status_code == 200
    ai_data = resp.json()
    assert "summary" in ai_data
    assert "risk_level" in ai_data
    # Verify API key is NOT in response
    assert "gsk_" not in str(ai_data)
    print("[PASS] /api/analytics/ai endpoint route verified without key exposure.")


if __name__ == "__main__":
    print("=== Running AI API & Excel/CSV Pipeline Tests ===")
    test_excel_upload_and_cleaning()
    test_ai_analysis_service_live_api()
    test_ai_endpoint_route()
    print("=== ALL AI & EXCEL TESTS PASSED SUCCESSFULLY! ===")
