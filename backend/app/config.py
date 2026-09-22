"""POLAR-EMS central configuration.

All physical parameters of the simulated station live here so the safety
engine, autonomy engine and simulator always agree on the same numbers.
Every value is SIMULATION / DEMONSTRATION DATA for the fictional station
"MAITRI SIMULATION" — not connected to any real Antarctic station.
"""
from __future__ import annotations

import os

def _load_env() -> None:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v

_load_env()

AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("GROQ_API_KEY", "")
AI_API_ENDPOINT = os.environ.get("AI_API_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
AI_MODEL = os.environ.get("AI_MODEL", "llama-3.3-70b-versatile")

# ---------------------------------------------------------------- station ---
STATION_ID = "maitri-sim"
STATION_NAME = "MAITRI SIMULATION"
SIMULATION_LABEL = "SIMULATION / DEMONSTRATION DATA"

# ------------------------------------------------------------------ power ---
DIESEL_RATED_KW = 500.0          # generator maximum output
DIESEL_MIN_KW = 50.0             # minimum stable output when running
DIESEL_FUEL_L_PER_KWH = 0.28     # specific fuel consumption (litres per kWh)
BATTERY_CAPACITY_KWH = 1200.0    # nominal capacity
BATTERY_MAX_CHARGE_KW = 300.0    # charge power limit
BATTERY_MAX_DISCHARGE_KW = 350.0 # discharge power limit
BATTERY_CHARGE_EFF = 0.95
BATTERY_DISCHARGE_EFF = 0.95
SOLAR_CAPACITY_KW = 120.0        # array peak
WIND_CAPACITY_KW = 150.0         # turbine rated output

# ----------------------------------------------------------------- safety ---
SAFETY_RULES = {
    "min_battery_soc": 30.0,     # % — optimizer must not plan below this
    "emergency_battery_soc": 20.0,  # % — triggers EMERGENCY mode
    "min_fuel_reserve_pct": 15.0,   # % of usable fuel capacity
    "generator_max_kw": DIESEL_RATED_KW,
    "generator_min_kw": DIESEL_MIN_KW,
    "critical_load_kw": 72.0,       # must never be shed
    "max_uncertainty_reserve_pct": 15.0,  # extra reserve for forecast error
}
USABLE_FUEL_L = 10000.0            # usable tank capacity

# ------------------------------------------------------------ mode thresholds
RESUPPLY_RISK_MARGIN_DAYS = 2.0    # autonomy margin below this => RESUPPLY RISK
CRITICAL_MARGIN_DAYS = 0.0         # negative margin => CRITICAL
EMERGENCY_FUEL_PCT = 8.0           # % of usable capacity

# ------------------------------------------------------------- forecasting ---
FORECAST_HORIZONS_H = [1, 6, 24]
FORECAST_HISTORY_H = 24 * 21       # training window (hours)
UNCERTAINTY_Z = 1.28               # ~90% prediction interval

# ------------------------------------------------------------- simulation ---
SIM_TICK_SECONDS = 2.0             # wall-clock seconds per simulation tick
SIM_HOURS_PER_TICK = 1.0 / 60.0    # 1 tick = 1 simulated minute (accelerated)
SEED_HISTORY_DAYS = 30             # pre-seeded history for analytics

# -------------------------------------------------------------- resupply ----
DEFAULT_RESUPPLY_IN_DAYS = 6
DEFAULT_RESUPPLY_FUEL_L = 6000.0

# ------------------------------------------------------------ connectivity ---
DATA_DIR = os.environ.get("POLAR_EMS_DATA", os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "polarems.db")
