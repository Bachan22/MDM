"""
POLAR-EMS Master Dataset Generator & Schema Audit Script
Generates 9 compatible Excel (.xlsx) telemetry datasets and POLAR_EMS_DATASET_SCHEMA.xlsx
"""
import os
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Output Directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

print(f"Generating POLAR-EMS Capstone Excel Datasets in: {DATA_DIR}")

# Seed for reproducible realistic datasets
np.random.seed(42)
random.seed(42)

# Helper function to generate telemetry time series
def generate_telemetry_df(
    station_name: str,
    start_dt: datetime,
    days: int,
    equip_id: str,
    stress_mode: bool = False,
    renewable_mode: bool = False,
    include_researcher: bool = False
) -> pd.DataFrame:
    records = []
    current_dt = start_dt
    total_hours = days * 24
    
    # Baseline parameters based on station
    base_temp = -15.0 if station_name == "Bharati" else -18.0 if station_name == "Maitri" else -22.0
    base_load = 110.0 if station_name == "Bharati" else 125.0 if station_name == "Maitri" else 95.0
    
    runtime = 1000.0
    
    for h in range(total_hours):
        dt_str = current_dt.strftime("%Y-%m-%d %H:%M:%S")
        day_of_year = current_dt.timetuple().tm_yday
        hour_of_day = current_dt.hour
        
        # Diurnal thermal variation
        temp = base_temp + 5.0 * np.sin(2 * np.pi * (hour_of_day - 6) / 24.0) + np.random.normal(0, 1.5)
        
        # Solar generation (zero during polar night in Antarctic winter: May-Aug)
        is_polar_night = 120 <= day_of_year <= 240
        if is_polar_night or hour_of_day < 6 or hour_of_day > 18:
            solar = 0.0
        else:
            peak_solar = 65.0 if renewable_mode else 45.0
            solar = max(0.0, peak_solar * np.sin(np.pi * (hour_of_day - 6) / 12.0) + np.random.normal(0, 3.0))
            
        # Wind speed & generation
        wind_speed = max(0.0, 8.5 + 4.0 * np.sin(2 * np.pi * day_of_year / 365.0) + np.random.normal(0, 2.5))
        wind_gen = max(0.0, min(80.0, (wind_speed / 15.0) ** 3 * 70.0 + np.random.normal(0, 2.0)))
        
        # Load & Energy consumption
        load_var = 25.0 * np.sin(2 * np.pi * (hour_of_day - 8) / 24.0) + np.random.normal(0, 5.0)
        equip_load = max(40.0, base_load + load_var)
        
        # Stress mode anomalies
        if stress_mode and random.random() < 0.05:
            equip_load += random.uniform(50.0, 95.0)
            temp += random.uniform(8.0, 14.0)
            status = "WARNING" if equip_load < 180 else "CRITICAL"
        else:
            status = "NORMAL"
            
        energy_kwh = max(10.0, equip_load * 1.05 + np.random.normal(0, 3.0))
        
        # Battery state of charge (%)
        if renewable_mode:
            bat_soc = max(35.0, min(100.0, 75.0 + 20.0 * np.sin(2 * np.pi * hour_of_day / 24.0) + np.random.normal(0, 3.0)))
        else:
            bat_soc = max(40.0, min(98.0, 82.0 - 0.1 * (equip_load - base_load) + np.random.normal(0, 2.0)))
            
        runtime += 1.0
        
        row = {
            "Timestamp": dt_str,
            "Station": station_name,
            "Energy_kWh": round(energy_kwh, 2),
            "Air_Temp_C": round(temp, 1),
            "Solar_kWh": round(solar, 2),
            "Wind_Velocity_ms": round(wind_speed, 1),
            "Wind_Gen_kW": round(wind_gen, 2),
            "Battery_SOC": round(bat_soc, 1),
            "Machine_Load_kW": round(equip_load, 2),
            "Equipment_ID": equip_id,
            "Equipment_Status": status,
            "Equipment_Runtime": round(runtime, 1)
        }
        
        if include_researcher:
            teams = ["Glaciology Alpha", "Meteorology Team B", "Astrophysics Grid", "Environmental Biology"]
            researchers = ["Dr. A. Sharma", "Dr. K. Larsen", "Prof. R. Vance", "Dr. S. Nair"]
            row["Researcher_Name"] = random.choice(researchers)
            row["Research_Team"] = random.choice(teams)
            row["Research_Activity"] = "Ice Core Sampling" if hour_of_day < 12 else "Telemetry Calibration"
            
        records.append(row)
        current_dt += timedelta(hours=1)
        
    return pd.DataFrame(records)

# ---------------------------------------------------------------- Data Generators ----

def create_dataset_1():
    print("Generating 01_Bharati_Full_History.xlsx...")
    df = generate_telemetry_df("Bharati", datetime(2025, 1, 1), 365, "Bharati-Gen-1")
    path = os.path.join(DATA_DIR, "01_Bharati_Full_History.xlsx")
    df.to_excel(path, sheet_name="Bharati_Telemetry", index=False)

def create_dataset_2():
    print("Generating 02_Maitri_Full_History.xlsx...")
    df = generate_telemetry_df("Maitri", datetime(2025, 1, 1), 365, "Maitri-Gen-1")
    path = os.path.join(DATA_DIR, "02_Maitri_Full_History.xlsx")
    df.to_excel(path, sheet_name="Maitri_Telemetry", index=False)

def create_dataset_3():
    print("Generating 03_Dakshin_Gangotri_Full_History.xlsx...")
    df = generate_telemetry_df("Dakshin Gangotri", datetime(2025, 1, 1), 365, "DG-Turbine-1")
    path = os.path.join(DATA_DIR, "03_Dakshin_Gangotri_Full_History.xlsx")
    df.to_excel(path, sheet_name="DG_Telemetry", index=False)

def create_dataset_4():
    print("Generating 04_MultiStation_Quarterly.xlsx...")
    df1 = generate_telemetry_df("Bharati", datetime(2026, 1, 1), 90, "Bharati-Gen-1")
    df2 = generate_telemetry_df("Maitri", datetime(2026, 1, 1), 90, "Maitri-Gen-2")
    df3 = generate_telemetry_df("Dakshin Gangotri", datetime(2026, 1, 1), 90, "DG-Plant-1")
    df_combo = pd.concat([df1, df2, df3], ignore_index=True)
    path = os.path.join(DATA_DIR, "04_MultiStation_Quarterly.xlsx")
    df_combo.to_excel(path, sheet_name="Quarterly_Telemetry", index=False)

def create_dataset_5():
    print("Generating 05_Research_Activity_Integrated.xlsx...")
    df = generate_telemetry_df("Bharati", datetime(2025, 6, 1), 60, "Bharati-Research-Gen", include_researcher=True)
    # Add optional price column to verify irrelevant column handling
    df["Tariff_Price_INR"] = 45.0
    path = os.path.join(DATA_DIR, "05_Research_Activity_Integrated.xlsx")
    df.to_excel(path, sheet_name="Research_Telemetry", index=False)

def create_dataset_6():
    print("Generating 06_Equipment_Health_Stress.xlsx...")
    df1 = generate_telemetry_df("Maitri", datetime(2025, 9, 1), 60, "Maitri-Main-Diesel", stress_mode=True)
    df2 = generate_telemetry_df("Bharati", datetime(2025, 9, 1), 60, "Bharati-Solar-Inverter", stress_mode=True)
    df_combo = pd.concat([df1, df2], ignore_index=True)
    path = os.path.join(DATA_DIR, "06_Equipment_Health_Stress.xlsx")
    df_combo.to_excel(path, sheet_name="Equipment_Stress", index=False)

def create_dataset_7():
    print("Generating 07_Resource_Risk_History.xlsx...")
    df1 = generate_telemetry_df("Dakshin Gangotri", datetime(2025, 5, 1), 90, "DG-Power-Plant")
    df2 = generate_telemetry_df("Maitri", datetime(2025, 5, 1), 90, "Maitri-Gen-3")
    df_combo = pd.concat([df1, df2], ignore_index=True)
    path = os.path.join(DATA_DIR, "07_Resource_Risk_History.xlsx")
    df_combo.to_excel(path, sheet_name="Resource_Risk", index=False)

def create_dataset_8():
    print("Generating 08_Renewable_Energy_History.xlsx...")
    df1 = generate_telemetry_df("Bharati", datetime(2025, 11, 1), 90, "Bharati-Renewables", renewable_mode=True)
    df2 = generate_telemetry_df("Maitri", datetime(2025, 11, 1), 90, "Maitri-Wind-Array", renewable_mode=True)
    df_combo = pd.concat([df1, df2], ignore_index=True)
    path = os.path.join(DATA_DIR, "08_Renewable_Energy_History.xlsx")
    df_combo.to_excel(path, sheet_name="Renewable_History", index=False)

def create_dataset_9_master():
    print("Generating 09_COMPLETE_DEMO_MASTER.xlsx...")
    # Full master year dataset for all 3 stations
    df1 = generate_telemetry_df("Bharati", datetime(2025, 1, 1), 365, "Bharati-Gen-1", renewable_mode=True)
    df2 = generate_telemetry_df("Maitri", datetime(2025, 1, 1), 365, "Maitri-Diesel-2", stress_mode=True)
    df3 = generate_telemetry_df("Dakshin Gangotri", datetime(2025, 1, 1), 365, "DG-Wind-1")
    df_master = pd.concat([df1, df2, df3], ignore_index=True)
    path = os.path.join(DATA_DIR, "09_COMPLETE_DEMO_MASTER.xlsx")
    df_master.to_excel(path, sheet_name="Master_Telemetry", index=False)

def create_schema_doc_excel():
    print("Generating POLAR_EMS_DATASET_SCHEMA.xlsx...")
    schema_path = os.path.join(DATA_DIR, "POLAR_EMS_DATASET_SCHEMA.xlsx")
    
    with pd.ExcelWriter(schema_path, engine="openpyxl") as writer:
        # Sheet 1 — Canonical Schema
        df_schema = pd.DataFrame([
            {"Field": "Timestamp", "Canonical": "timestamp", "Type": "datetime", "Required": "YES", "Unit": "YYYY-MM-DD HH:mm:ss", "Description": "Telemetry reading timestamp UTC"},
            {"Field": "Station", "Canonical": "station", "Type": "string", "Required": "NO (Default: Station-A)", "Unit": "Name", "Description": "Antarctic research station identifier"},
            {"Field": "Energy_kWh", "Canonical": "energy_consumption", "Type": "float", "Required": "NO", "Unit": "kWh", "Description": "Gross electrical energy consumption"},
            {"Field": "Air_Temp_C", "Canonical": "temperature", "Type": "float", "Required": "NO", "Unit": "°C", "Description": "Ambient outside air temperature"},
            {"Field": "Solar_kWh", "Canonical": "solar_generation", "Type": "float", "Required": "NO", "Unit": "kW / kWh", "Description": "Solar photovoltaic energy generation"},
            {"Field": "Wind_Velocity_ms", "Canonical": "wind_speed", "Type": "float", "Required": "NO", "Unit": "m/s", "Description": "Wind velocity measurement"},
            {"Field": "Wind_Gen_kW", "Canonical": "wind_generation", "Type": "float", "Required": "NO", "Unit": "kW", "Description": "Wind turbine electrical generation"},
            {"Field": "Battery_SOC", "Canonical": "battery_level", "Type": "float", "Required": "NO", "Unit": "% (0-100)", "Description": "Battery state of charge percentage"},
            {"Field": "Machine_Load_kW", "Canonical": "equipment_load", "Type": "float", "Required": "NO", "Unit": "kW", "Description": "Operating machine/plant demand load"},
            {"Field": "Equipment_ID", "Canonical": "equipment_id", "Type": "string", "Required": "NO", "Unit": "ID", "Description": "Monitored generator or plant asset ID"},
            {"Field": "Equipment_Status", "Canonical": "equipment_status", "Type": "string", "Required": "NO", "Unit": "Status", "Description": "Operational state (NORMAL, WARNING, CRITICAL)"},
            {"Field": "Equipment_Runtime", "Canonical": "equipment_runtime", "Type": "float", "Required": "NO", "Unit": "Hours", "Description": "Cumulative operating runtime hours"},
            {"Field": "Failure_Label", "Canonical": "failure_label", "Type": "int / bool", "Required": "NO", "Unit": "0 / 1", "Description": "Binary breakdown indicator (optional)"}
        ])
        df_schema.to_excel(writer, sheet_name="Canonical Schema", index=False)
        
        # Sheet 2 — Module Dependencies
        df_deps = pd.DataFrame([
            {"Field": "timestamp", "Overview": "✓", "Energy": "✓", "Equipment": "✓", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "station", "Overview": "✓", "Energy": "✓", "Equipment": "✓", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "energy_consumption", "Overview": "✓", "Energy": "✓", "Equipment": "Optional", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "temperature", "Overview": "✓", "Energy": "✓", "Equipment": "✓", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "equipment_load", "Overview": "✓", "Energy": "✓", "Equipment": "✓", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "battery_level", "Overview": "✓", "Energy": "Optional", "Equipment": "Optional", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "solar_generation", "Overview": "Optional", "Energy": "✓", "Equipment": "Optional", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "wind_speed", "Overview": "Optional", "Energy": "✓", "Equipment": "Optional", "Resource Risk": "✓", "AI Insights": "✓", "Export Report": "✓"},
            {"Field": "equipment_id", "Overview": "✓", "Energy": "Optional", "Equipment": "✓", "Resource Risk": "Optional", "AI Insights": "✓", "Export Report": "✓"}
        ])
        df_deps.to_excel(writer, sheet_name="Module Dependencies", index=False)

        # Sheet 3 — Accepted Aliases
        df_aliases = pd.DataFrame([
            {"Canonical": "timestamp", "Accepted Aliases": "timestamp, time, date, datetime, date_time, recorded_at, reading_time, measurement_time, ts, dt"},
            {"Canonical": "station", "Accepted Aliases": "station, station_id, station_name, facility, site, base, location, base_id, station_code"},
            {"Canonical": "energy_consumption", "Accepted Aliases": "energy_consumption, energy_kwh, energy_used, power_consumption, consumption, consumption_kwh, energy"},
            {"Canonical": "temperature", "Accepted Aliases": "temperature, air_temperature, temp_c, temp, ambient_temp, outside_temp, air_temp, temperature_c"},
            {"Canonical": "solar_generation", "Accepted Aliases": "solar_generation, solar_kw, solar_power, solar_pv, pv_generation, solar, pv_output, solar_kwh"},
            {"Canonical": "wind_speed", "Accepted Aliases": "wind_speed, wind_ms, wind_speed_ms, wind_velocity, wind, wind_speed_mps, wind_spd"},
            {"Canonical": "battery_level", "Accepted Aliases": "battery_level, battery_soc, battery_pct, soc, soc_pct, battery_percentage, battery_storage_pct"},
            {"Canonical": "equipment_load", "Accepted Aliases": "equipment_load, load_kw, machine_load, generator_load, operating_load, equipment_demand_kw"}
        ])
        df_aliases.to_excel(writer, sheet_name="Accepted Aliases", index=False)

        # Sheet 4 — Units
        df_units = pd.DataFrame([
            {"Field": "energy_consumption", "Unit": "kWh", "Range": "> 0.0"},
            {"Field": "temperature", "Unit": "°C", "Range": "-60.0 to +30.0"},
            {"Field": "solar_generation", "Unit": "kW / kWh", "Range": ">= 0.0"},
            {"Field": "wind_speed", "Unit": "m/s", "Range": ">= 0.0"},
            {"Field": "battery_level", "Unit": "%", "Range": "0.0 to 100.0"},
            {"Field": "equipment_load", "Unit": "kW", "Range": ">= 0.0"}
        ])
        df_units.to_excel(writer, sheet_name="Units", index=False)

        # Sheet 5 — Station Directory
        df_stations = pd.DataFrame([
            {"Station Name": "Bharati", "Location": "Larsemann Hills (69°24'S, 76°11'E)", "Primary Resource": "Solar + Diesel + Storage"},
            {"Station Name": "Maitri", "Location": "Schirmacher Oasis (70°45'S, 11°44'E)", "Primary Resource": "Diesel + Thermal + Storage"},
            {"Station Name": "Dakshin Gangotri", "Location": "Ice Shelf (70°05'S, 12°00'E)", "Primary Resource": "Wind + Diesel Reserve"}
        ])
        df_stations.to_excel(writer, sheet_name="Station Directory", index=False)

        # Sheet 6 — Researcher Note
        df_researcher = pd.DataFrame([
            {"Topic": "Researcher Context Columns", "Details": "Optional columns like Researcher_Name or Research_Team are preserved in dataset metadata and raw_json without interfering with core operational telemetry mapping."}
        ])
        df_researcher.to_excel(writer, sheet_name="Researcher Note", index=False)

        # Sheet 7 — Dataset Recommendations
        df_recs = pd.DataFrame([
            {"Dataset File": "09_COMPLETE_DEMO_MASTER.xlsx", "Recommended Purpose": "RECOMMENDED MASTER CAPSTONE DEMO (All 3 Stations, Full Year, Dense Telemetry)", "Coverage": "Bharati, Maitri, Dakshin Gangotri"},
            {"Dataset File": "01_Bharati_Full_History.xlsx", "Recommended Purpose": "Single Station Annual Analysis (Bharati)", "Coverage": "Full Year 2025"},
            {"Dataset File": "02_Maitri_Full_History.xlsx", "Recommended Purpose": "Single Station Annual Analysis (Maitri)", "Coverage": "Full Year 2025"},
            {"Dataset File": "03_Dakshin_Gangotri_Full_History.xlsx", "Recommended Purpose": "Single Station Annual Analysis (Dakshin Gangotri)", "Coverage": "Full Year 2025"},
            {"Dataset File": "04_MultiStation_Quarterly.xlsx", "Recommended Purpose": "Multi-Station Network Comparison", "Coverage": "Q1 2026 (All 3 Stations)"},
            {"Dataset File": "05_Research_Activity_Integrated.xlsx", "Recommended Purpose": "Research Team Activity & Optional Column Ingestion Test", "Coverage": "Bharati 60 Days"},
            {"Dataset File": "06_Equipment_Health_Stress.xlsx", "Recommended Purpose": "Equipment Health Anomaly & Stress Signal Test", "Coverage": "Maitri & Bharati"},
            {"Dataset File": "07_Resource_Risk_History.xlsx", "Recommended Purpose": "Station Resource Risk & Reserve Stress Evaluation", "Coverage": "Dakshin Gangotri & Maitri"},
            {"Dataset File": "08_Renewable_Energy_History.xlsx", "Recommended Purpose": "Renewable Coverage vs Demand Analysis", "Coverage": "Bharati & Maitri"}
        ])
        df_recs.to_excel(writer, sheet_name="Dataset Recommendations", index=False)

if __name__ == "__main__":
    create_dataset_1()
    create_dataset_2()
    create_dataset_3()
    create_dataset_4()
    create_dataset_5()
    create_dataset_6()
    create_dataset_7()
    create_dataset_8()
    create_dataset_9_master()
    create_schema_doc_excel()
    print("All 9 datasets and POLAR_EMS_DATASET_SCHEMA.xlsx generated successfully!")
