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
    risk_level: str
    main_driver: str
    current_value: str
    historical_average: str
    evidence_text: str


class StationResourceRiskAnalytics(BaseModel):
    has_data: bool
    stations_analyzed: int
    high_risk_stations_count: int
    moderate_risk_stations_count: int
    low_risk_stations_count: int
    overall_network_risk: str
    station_risks: List[StationResourceRiskItem] = Field(default_factory=list)
    station_risk_comparison: List[Dict[str, Any]] = Field(default_factory=list)
    battery_available: bool = False
    renewable_available: bool = False
    ai_insights: Optional[Dict[str, Any]] = None
    missing_fields_notice: List[str] = Field(default_factory=list)


class OverviewAnalytics(BaseModel):
    has_data: bool
    dataset_status: MdmStatus
    energy_summary: Dict[str, Any]
    equipment_summary: Dict[str, Any]
    resource_risk_summary: Dict[str, Any]
    ai_management_insights: List[Dict[str, Any]] = Field(default_factory=list)


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
    record_count: int
    points: List[AggregatedPoint] = Field(default_factory=list)
    available_calendar_dates: List[str] = Field(default_factory=list)
    missing_notice: Optional[str] = None

