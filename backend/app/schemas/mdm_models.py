"""Pydantic schemas for Polar-EMS Management Data Analytics (MDM)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetMetadata(BaseModel):
    id: str
    filename: str
    upload_timestamp: float
    rows_detected: int
    rows_accepted: int
    rows_rejected: int
    columns_detected: List[str]
    columns_mapped: Dict[str, str]
    columns_ignored: List[str]
    duplicates_removed: int
    missing_values_handled: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    stations: List[str] = Field(default_factory=list)
    file_size_bytes: int = 0


class UploadResponse(BaseModel):
    success: bool
    dataset_id: str
    filename: str
    rows_detected: int
    rows_accepted: int
    rows_rejected: int
    columns_detected: List[str]
    columns_mapped: Dict[str, str]
    columns_ignored: List[str]
    duplicates_removed: int
    missing_values_handled: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    stations_detected: List[str] = Field(default_factory=list)
    merge_status: str
    message: str


class MdmStatus(BaseModel):
    has_data: bool
    records_count: int
    stations_count: int
    stations: List[str] = Field(default_factory=list)
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    datasets_count: int
    available_variables: List[str] = Field(default_factory=list)
    datasets: List[DatasetMetadata] = Field(default_factory=list)
    missing_values_count: int = 0
    missing_values_pct: float = 0.0
    data_quality_pct: float = 100.0
    valid_records_count: int = 0
    rows_detected_count: int = 0
    rows_rejected_count: int = 0


class EnergyAnalytics(BaseModel):
    has_data: bool
    data_period: Dict[str, Optional[str]]
    total_energy_kwh: Optional[float] = None
    total_energy_unit: str = "kWh"
    avg_power_kw: Optional[float] = None
    peak_demand_kw: Optional[float] = None
    min_demand_kw: Optional[float] = None
    avg_equipment_load_kw: Optional[float] = None
    trend_direction: Optional[str] = None
    trend_pct: Optional[float] = None
    consumption_by_station: Dict[str, float] = Field(default_factory=dict)
    time_series: List[Dict[str, Any]] = Field(default_factory=list)
    temp_vs_energy: List[Dict[str, Any]] = Field(default_factory=list)
    load_vs_energy: List[Dict[str, Any]] = Field(default_factory=list)
    renewable_vs_consumption: Optional[List[Dict[str, Any]]] = None
    renewable_available: bool = False
    ai_insights: Optional[Dict[str, Any]] = None
    missing_fields_notice: List[str] = Field(default_factory=list)


class EquipmentHealthRecord(BaseModel):
    equipment_id: str
    station: str
    risk_level: str
    main_signal: str
    anomaly_count: int
    last_observed: str
    operating_temp_c: Optional[float] = None
    current_load_kw: Optional[float] = None


class EquipmentHealthAnalytics(BaseModel):
    has_data: bool
    records_analyzed: int
    anomalies_detected: int
    high_risk_signals_count: int
    overall_risk_level: str
    has_true_failure_labels: bool = False
    methodology_note: str
    equipment_records: List[EquipmentHealthRecord] = Field(default_factory=list)
    anomaly_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    load_trend: List[Dict[str, Any]] = Field(default_factory=list)
    temp_vs_load: List[Dict[str, Any]] = Field(default_factory=list)
    ai_insights: Optional[Dict[str, Any]] = None
    missing_fields_notice: List[str] = Field(default_factory=list)


class StationResourceRiskItem(BaseModel):
    station: str
    resource: str
    risk_level: str  # Kept for backward compatibility
    current_risk_level: str = "LOW"
    forecast_risk_level: Optional[str] = None
    main_driver: str
    forecast_driver_reason: Optional[str] = None
    current_value: str
    historical_average: str
    evidence_text: str


class StationResourceRiskAnalytics(BaseModel):
    has_data: bool
    stations_analyzed: int
    high_risk_stations_count: int
    moderate_risk_stations_count: int
    low_risk_stations_count: int
    overall_network_risk: str  # Kept for backward compatibility
    network_current_risk: str = "LOW"
    network_forecast_risk: Optional[str] = None
    forecast_horizon_hours: int = 24
    forecast_summary: Optional[str] = None
    station_risks: List[StationResourceRiskItem] = Field(default_factory=list)
    station_risk_comparison: List[Dict[str, Any]] = Field(default_factory=list)
    battery_available: bool = False
    renewable_available: bool = False
    ai_insights: Optional[Dict[str, Any]] = None
    missing_fields_notice: List[str] = Field(default_factory=list)


class OperationalContext(BaseModel):
    station: str
    anchor_date: Optional[str] = None
    forecast_horizon_hours: int = 24
    energy: Dict[str, Any] = Field(default_factory=dict)
    forecast: Dict[str, Any] = Field(default_factory=dict)
    battery: Dict[str, Any] = Field(default_factory=dict)
    renewable: Dict[str, Any] = Field(default_factory=dict)
    equipment: Dict[str, Any] = Field(default_factory=dict)
    resource_risk: Dict[str, Any] = Field(default_factory=dict)
    signal_availability: Dict[str, str] = Field(default_factory=dict)
    missing_notices: List[str] = Field(default_factory=list)


class OverviewAnalytics(BaseModel):
    has_data: bool
    dataset_status: MdmStatus
    energy_summary: Dict[str, Any]
    equipment_summary: Dict[str, Any]
    resource_risk_summary: Dict[str, Any]
    ai_management_insights: List[Dict[str, Any]] = Field(default_factory=list)
    dynamic_ai_insights: Optional[Dict[str, Any]] = None


class AggregatedPoint(BaseModel):
    key: str
    label: str
    full_date_label: str
    value: float
    record_count: int
    is_peak: bool = False
    is_lowest: bool = False
    has_data: bool = True
    change_pct: Optional[float] = None


class PeriodAggregationResponse(BaseModel):
    has_data: bool
    period: str
    period_label: str
    anchor_date: str
    current_total: float
    previous_total: Optional[float] = None
    trend_pct: Optional[float] = None
    trend_direction: Optional[str] = None
    avg_consumption: Optional[float] = None
    peak_value: Optional[float] = None
    peak_label: Optional[str] = None
    lowest_value: Optional[float] = None
    lowest_label: Optional[str] = None
    record_count: int = 0
    points: List[AggregatedPoint] = Field(default_factory=list)
    available_calendar_dates: List[str] = Field(default_factory=list)
    missing_notice: Optional[str] = None


class WeatherLoadForecastPoint(BaseModel):
    timestamp: str
    predicted_load_kw: float
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None


class HistoricalTelemetryPoint(BaseModel):
    timestamp: str
    actual_load_kw: float
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None


class WeatherLoadForecastResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    model: str = "POLAR EMS Weather Load Forecaster"
    station: str = "Bharati"
    generated_at: str = ""
    forecast_horizon_hours: int = 24
    current_load_kw: Optional[float] = None
    predicted_peak_kw: Optional[float] = None
    predicted_average_kw: Optional[float] = None
    predicted_min_kw: Optional[float] = None
    peak_time: Optional[str] = None
    recent_load_avg_kw: Optional[float] = None
    recent_load_peak_kw: Optional[float] = None
    trend: Optional[str] = None
    records_available: Optional[int] = None
    records_required: Optional[int] = None
    historical_points: List[HistoricalTelemetryPoint] = Field(default_factory=list)
    forecast_points: List[WeatherLoadForecastPoint] = Field(default_factory=list)
    ai_interpretation: Optional[Dict[str, Any]] = None
    model_status: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# ENERGY RESERVE & SUSTAINABILITY SCHEMAS
# ---------------------------------------------------------------------------

class LoadTierAllocation(BaseModel):
    tier_name: str
    tier_label: str
    priority: int
    configured_share_pct: float
    required_power_kw: float
    allocated_power_kw: float
    allocation_pct: float
    load_items: List[str] = Field(default_factory=list)
    status: str = "FULFILLED"


class EnergyDepletionScenario(BaseModel):
    name: str
    label: str
    daily_consumption_kwh: float
    estimated_days_remaining: Optional[float] = None
    projected_depletion_date: Optional[str] = None
    description: str


class ReserveForecastPoint(BaseModel):
    day: int
    date: str
    baseline_reserve_pct: float
    baseline_reserve_kwh: float
    forecast_adjusted_reserve_pct: Optional[float] = None
    forecast_adjusted_reserve_kwh: Optional[float] = None
    conservation_reserve_pct: Optional[float] = None
    conservation_reserve_kwh: Optional[float] = None
    high_demand_reserve_pct: Optional[float] = None
    high_demand_reserve_kwh: Optional[float] = None


class EnergyReservePolicy(BaseModel):
    safe_days: float = 30.0
    watch_days: float = 15.0
    conserve_days: float = 7.0
    critical_days: float = 3.0
    configured_capacity_kwh: Optional[float] = None


class EnergyReserveAnalytics(BaseModel):
    has_data: bool
    has_reserve_data: bool
    station: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    latest_timestamp: Optional[str] = None

    # Reserve quantities
    available_energy_kwh: Optional[float] = None
    battery_soc_pct: Optional[float] = None
    storage_capacity_kwh: Optional[float] = None
    reserve_notice: Optional[str] = None

    # Consumption rates across multiple windows
    daily_consumption_24h_kwh: Optional[float] = None
    daily_consumption_7d_kwh: Optional[float] = None
    daily_consumption_30d_kwh: Optional[float] = None
    daily_consumption_baseline_kwh: Optional[float] = None
    daily_consumption_peak_kwh: Optional[float] = None
    daily_consumption_forecast_kwh: Optional[float] = None

    # Trend
    consumption_trend_pct: Optional[float] = None
    consumption_trend_direction: str = "Stable"

    # Days Remaining & Estimates
    estimated_days_baseline: Optional[float] = None
    estimated_days_forecast_adjusted: Optional[float] = None
    estimated_days_high_demand: Optional[float] = None
    estimated_days_conservation: Optional[float] = None
    projected_depletion_date: Optional[str] = None

    # Sustainability Status
    sustainability_status: str = "DATA_REQUIRED"
    sustainability_badge_color: str = "cyan"

    # Policy thresholds
    policy: EnergyReservePolicy = Field(default_factory=EnergyReservePolicy)

    # Scenarios
    scenarios: List[EnergyDepletionScenario] = Field(default_factory=list)

    # Load Allocation
    total_required_power_kw: float = 0.0
    total_available_power_kw: float = 0.0
    power_shortfall_kw: float = 0.0
    critical_loads_supported: bool = True
    load_allocations: List[LoadTierAllocation] = Field(default_factory=list)

    # Conservation recommendations
    conservation_mode_recommended: bool = False
    recommended_reductions: Dict[str, str] = Field(default_factory=dict)
    recommended_action_text: str = ""

    # Alerts
    alerts: List[Dict[str, Any]] = Field(default_factory=list)

    # Reserve depletion trajectory
    reserve_forecast_trajectory: List[ReserveForecastPoint] = Field(default_factory=list)

    # AI Interpretation
    ai_interpretation: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# GROUNDED AI OPERATIONAL DECISION-SUPPORT SCHEMAS
# ---------------------------------------------------------------------------

class EnergyRiskWindow(BaseModel):
    window: str
    peak_kw: Optional[float] = None
    reason: str
    severity: str = "HIGH"


class EnergyChargingWindow(BaseModel):
    window: str
    action: str
    favorable_factors: List[str] = Field(default_factory=list)


class EnergyReserveAIResponse(BaseModel):
    status: str = "success"  # "success" | "fallback" | "data_required"
    station: str = "Bharati"
    forecast_horizon_hours: int = 24
    anchor_date: Optional[str] = None

    # Deterministic Operational Status from Backend
    energy_status: str = "NORMAL"  # "NORMAL" | "WATCH" | "CONSERVE" | "CRITICAL"
    status_badge_color: str = "#22c55e"

    # Grounded Narrative Explanations
    energy_situation: str
    forecast_impact: str
    reserve_recommendation: str
    critical_window: Optional[EnergyRiskWindow] = None
    charging_opportunity: Optional[EnergyChargingWindow] = None
    recommended_actions: List[str] = Field(default_factory=list)
    why: str

    # Verified Grounded Evidence
    evidence: Dict[str, Any] = Field(default_factory=dict)

    # Signal Classification (Observed, Forecasted, Unavailable)
    signal_availability: Dict[str, str] = Field(default_factory=dict)
    missing_data_notices: List[str] = Field(default_factory=list)

    source: str = "Empirical Grounding Engine"


# ---------------------------------------------------------------------------
# CONNECTED OPERATOR INSIGHT & TREND SCHEMAS
# ---------------------------------------------------------------------------

class EnergyTrendAnalysis(BaseModel):
    has_data: bool = True
    consumption_trend_pct: Optional[float] = None
    consumption_trend_direction: str = "Stable"
    average_demand_kw: Optional[float] = None
    peak_demand_kw: Optional[float] = None
    min_demand_kw: Optional[float] = None
    demand_stress_pct: Optional[float] = None
    highest_consuming_station: Optional[str] = None
    station_shares: Dict[str, float] = Field(default_factory=dict)
    equipment_load_change_pct: Optional[float] = None
    equipment_association_note: Optional[str] = None
    trend_summary: str = ""


class OperatorInsightResponse(BaseModel):
    status: str = "success"  # "success" | "fallback" | "data_required"
    station: str = "All"
    anchor_date: Optional[str] = None
    forecast_horizon_hours: int = 24
    priority_level: int = 7
    priority_title: str = "Normal Operating Conditions"

    # Analytical Operational Status (No UI colors - frontend controls styling)
    energy_status: str = "NORMAL"  # "NORMAL" | "WATCH" | "CONSERVE" | "CRITICAL"

    # 4-Step Operational Narrative Chain
    trend_analysis: EnergyTrendAnalysis = Field(default_factory=EnergyTrendAnalysis)
    current_situation: str
    forecast_impact: str
    operational_consequence: str
    recommended_actions: List[str] = Field(default_factory=list)

    # Underlying Data Context (For state synchronization, not a separate UI section)
    underlying_metrics: Dict[str, Any] = Field(default_factory=dict)

    # Signal Availability & Transparency
    signal_availability: Dict[str, str] = Field(default_factory=dict)
    missing_data_notices: List[str] = Field(default_factory=list)

    source: str = "Connected Energy Intelligence Engine"




