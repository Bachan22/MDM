"""Automated test suite for AI Analyst Chat functionality."""
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_chat_tests():
    print("=== Step 1: Chat Empty State (No Uploaded Data) ===")
    client.delete("/api/data/clear")

    resp_empty = client.post("/api/analytics/chat", json={
        "message": "What is the peak energy consumption?",
        "dashboard_context": {},
        "history": []
    })
    assert resp_empty.status_code == 200
    data_empty = resp_empty.json()
    assert "No dataset is currently uploaded" in data_empty["answer"]
    print("[PASS] AI Analyst handles empty state honestly.")

    print("\n=== Step 2: Upload Multi-Station Dataset ===")
    csv_data = """Time,Station_ID,Temperature_C,Power_kW,Battery_SOC,Equipment_Load_kW,Wind_Speed_ms
2026-09-01 00:00:00,Maitri,-18.0,140.0,85.0,110.0,8.0
2026-09-01 01:00:00,Maitri,-19.0,150.0,82.0,118.0,8.5
2026-09-01 02:00:00,Maitri,-21.0,190.0,75.0,160.0,11.0
2026-09-01 03:00:00,Maitri,-23.0,225.0,68.0,195.0,13.5
2026-09-01 04:00:00,Maitri,-25.0,240.0,60.0,210.0,15.0
2026-09-01 00:00:00,Bharati,-14.0,105.0,92.0,80.0,5.0
2026-09-01 01:00:00,Bharati,-14.5,108.0,90.0,82.0,5.5
"""
    up_resp = client.post(
        "/api/data/upload",
        files={"file": ("station_telemetry_chat.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    )
    assert up_resp.status_code == 200
    print("[PASS] Dataset uploaded successfully.")

    print("\n=== Step 3: Test Dataset Metadata Question ===")
    resp_meta = client.post("/api/analytics/chat", json={
        "message": "What data are you using?",
        "dashboard_context": {"selected_station": "All"},
        "history": []
    })
    assert resp_meta.status_code == 200
    data_meta = resp_meta.json()
    assert "answer" in data_meta
    assert len(data_meta["key_metrics"]) > 0
    assert "gsk_" not in str(data_meta)  # Zero key exposure
    print(f"[PASS] Metadata question answered: {data_meta['answer'][:90]}...")

    print("\n=== Step 4: Test Energy Consumption Question ===")
    resp_energy = client.post("/api/analytics/chat", json={
        "message": "Why did energy consumption increase this week?",
        "dashboard_context": {"selected_station": "Maitri"},
        "history": []
    })
    assert resp_energy.status_code == 200
    data_energy = resp_energy.json()
    assert "answer" in data_energy
    assert len(data_energy["key_metrics"]) > 0
    print(f"[PASS] Energy question answered: {data_energy['answer'][:90]}...")

    print("\n=== Step 5: Test Equipment Anomalies Question ===")
    resp_eq = client.post("/api/analytics/chat", json={
        "message": "Which equipment shows abnormal behavior?",
        "dashboard_context": {"selected_station": "Maitri"},
        "history": []
    })
    assert resp_eq.status_code == 200
    data_eq = resp_eq.json()
    assert "answer" in data_eq
    assert len(data_eq["evidence"]) > 0
    print(f"[PASS] Equipment anomaly question answered: {data_eq['answer'][:90]}...")

    print("\n=== Step 6: Test Station Resource Risk Question ===")
    resp_risk = client.post("/api/analytics/chat", json={
        "message": "Which station has the highest resource risk?",
        "dashboard_context": {"selected_station": "All"},
        "history": []
    })
    assert resp_risk.status_code == 200
    data_risk = resp_risk.json()
    assert "answer" in data_risk
    print(f"[PASS] Station resource risk question answered: {data_risk['answer'][:90]}...")

    print("\n=== Step 7: Test Conversational Follow-Up Turn ===")
    resp_followup = client.post("/api/analytics/chat", json={
        "message": "What about Bharati station?",
        "dashboard_context": {"selected_station": "Bharati"},
        "history": [
            {"role": "user", "content": "Which station has the highest resource risk?"},
            {"role": "assistant", "content": data_risk["answer"]}
        ]
    })
    assert resp_followup.status_code == 200
    data_followup = resp_followup.json()
    assert "answer" in data_followup
    print(f"[PASS] Follow-up question answered: {data_followup['answer'][:90]}...")

    print("\n=== ALL AI ANALYST CHAT TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_chat_tests()
