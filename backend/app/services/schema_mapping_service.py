"""Schema detection and semantic column mapping service for Polar-EMS MDM."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Canonical mapping aliases
CANONICAL_ALIASES: Dict[str, List[str]] = {
    "timestamp": [
        "timestamp", "time", "date", "datetime", "date_time", "recorded_at",
        "reading_time", "measurement_time", "ts", "dt", "datetime_utc",
        "record_time", "sample_time"
    ],
    "station": [
        "station", "station_id", "station_name", "facility", "site", "base",
        "location", "base_id", "station_code", "research_station"
    ],
    "energy_consumption": [
        "energy_consumption", "energy_kwh", "energy_used", "power_consumption",
        "consumption", "consumption_kwh", "energy", "load_consumption",
        "total_energy", "grid_load", "energy_consumption_kwh", "power_kwh",
        "power_demand", "total_demand_kw", "energy_consumed"
    ],
    "temperature": [
        "temperature", "air_temperature", "temp_c", "temp", "ambient_temp",
        "outside_temp", "outdoor_temp", "surface_temp", "temp_ambient",
        "air_temp", "temperature_c"
    ],
    "solar_generation": [
        "solar_generation", "solar_kw", "solar_power", "solar_pv",
        "pv_generation", "solar", "pv_output", "solar_generation_kw",
        "solar_kwh", "pv_power"
    ],
    "wind_speed": [
        "wind_speed", "wind_ms", "wind_speed_ms", "wind_velocity", "wind",
        "wind_speed_mps", "wind_spd"
    ],
    "wind_generation": [
        "wind_generation", "wind_kw", "wind_power", "turbine_output",
        "wind_gen_kw", "wind_generation_kw"
    ],
    "battery_level": [
        "battery_level", "battery_soc", "battery_pct", "soc", "soc_pct",
        "battery_percentage", "battery_storage_pct", "battery_state_of_charge",
        "battery_level_pct", "battery_charge"
    ],
    "equipment_load": [
        "equipment_load", "load_kw", "machine_load", "generator_load",
        "operating_load", "equipment_demand_kw", "plant_load", "critical_load",
        "active_load_kw", "equipment_power", "equipment_kw", "equip_load"
    ],
    "equipment_id": [
        "equipment_id", "machine_id", "asset_id", "unit_id", "generator_id",
        "component", "equipment_name", "asset_name", "device_id"
    ],
    "equipment_status": [
        "equipment_status", "status", "machine_status", "state",
        "operational_status", "health_status", "operating_state"
    ],
    "equipment_runtime": [
        "equipment_runtime", "runtime_hours", "operating_hours", "runtime",
        "run_hours", "service_hours", "operating_time_h"
    ],
    "failure_label": [
        "failure_label", "failure", "failure_event", "breakdown", "error_flag",
        "is_failure", "maintenance_required", "fault", "alarm_critical"
    ]
}

FINANCIAL_PATTERNS = [
    r"^price", r"^cost", r"^revenue", r"^tariff", r"^billing", r"^money",
    r"^transaction", r"^amount", r"^currency", r"^dollar", r"^inr", r"^eur"
]

IRRELEVANT_PATTERNS = [
    r"^operator", r"^user", r"^id$", r"^uuid", r"^session", r"^comment",
    r"^note", r"^index", r"^unnamed"
]


def normalize_col_name(col: str) -> str:
    """Normalize raw header string to snake_case alphanumeric."""
    cleaned = col.strip().lower()
    cleaned = re.sub(r"[^\w\s]", "_", cleaned)
    cleaned = re.sub(r"[\s_]+", "_", cleaned)
    return cleaned.strip("_")


def map_columns(headers: List[str]) -> Tuple[Dict[str, str], List[str], Dict[str, str]]:
    """
    Analyzes raw CSV headers and categorizes them:
    Returns:
      - mapped_columns: Dict[raw_header, canonical_name]
      - ignored_columns: List[raw_header]
      - classification: Dict[raw_header, 'Relevant'|'Ignored / Financial'|'Unknown / Irrelevant']
    """
    mapped_columns: Dict[str, str] = {}
    ignored_columns: List[str] = []
    classification: Dict[str, str] = {}

    # Invert canonical aliases for exact lookup
    alias_to_canonical: Dict[str, str] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        for alias in aliases:
            alias_to_canonical[normalize_col_name(alias)] = canonical

    # Track which canonical names are already assigned to avoid duplicate mapping
    assigned_canonicals = set()

    for raw in headers:
        norm = normalize_col_name(raw)

        # Check financial
        if any(re.search(pat, norm) for pat in FINANCIAL_PATTERNS):
            ignored_columns.append(raw)
            classification[raw] = "Ignored / Financial"
            continue

        # Check exact alias match
        if norm in alias_to_canonical:
            canonical = alias_to_canonical[norm]
            if canonical not in assigned_canonicals:
                mapped_columns[raw] = canonical
                assigned_canonicals.add(canonical)
                classification[raw] = "Relevant"
                continue

        # Check partial/contains matching
        matched_canonical = None
        for canonical, aliases in CANONICAL_ALIASES.items():
            if canonical in assigned_canonicals:
                continue
            for alias in aliases:
                norm_alias = normalize_col_name(alias)
                if norm_alias in norm or norm in norm_alias:
                    matched_canonical = canonical
                    break
            if matched_canonical:
                break

        if matched_canonical:
            mapped_columns[raw] = matched_canonical
            assigned_canonicals.add(matched_canonical)
            classification[raw] = "Relevant"
        elif any(re.search(pat, norm) for pat in IRRELEVANT_PATTERNS):
            ignored_columns.append(raw)
            classification[raw] = "Unknown / Irrelevant"
        else:
            ignored_columns.append(raw)
            classification[raw] = "Potentially Relevant / Unused"

    return mapped_columns, ignored_columns, classification
