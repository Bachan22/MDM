"""FastAPI Router for Polar-EMS Management Data Analytics (MDM)."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ..schemas.mdm_models import (
    EnergyAnalytics,
    EnergyReserveAIResponse,
    EnergyReserveAnalytics,
    EquipmentHealthAnalytics,
    MdmStatus,
    OperatorInsightResponse,
    OverviewAnalytics,
    PeriodAggregationResponse,
    StationResourceRiskAnalytics,
    UploadResponse,
    WeatherLoadForecastResponse,
)
from ..services.ai_analysis_service import AIAnalysisService
from ..services.data_cleaning_service import clean_dataset_bytes
from ..services.energy_analysis_service import calculate_energy_analytics
from ..services.energy_reserve_service import (
    calculate_energy_reserve_analytics,
    get_energy_reserve_ai_analysis,
)
from ..services.equipment_health_service import calculate_equipment_health_analytics
from ..services.forecasting_service import generate_weather_load_forecast
from ..services.mdm_aggregation_service import aggregate_mdm_period
from ..services.mdm_storage_service import (
    clear_mdm_data,
    get_mdm_status,
    save_cleaned_dataset,
)
from ..services.operator_insight_service import generate_operator_insight
from ..services.resource_risk_service import calculate_station_resource_risk

router = APIRouter(tags=["MDM Analytics"])



@router.post("/data/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Query(None)
):
    """Uploads, validates, cleans, deduplicates and merges CSV and Excel (.xlsx, .xls) datasets."""
    fn_lower = file.filename.lower()
    if not (fn_lower.endswith(".csv") or fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .csv, .xlsx, or .xls file."
        )

    content_bytes = await file.read()
    cleaned_result = clean_dataset_bytes(
        file_bytes=content_bytes,
        filename=file.filename,
        sheet_name=sheet_name
    )

    if not cleaned_result.get("success"):
        raise HTTPException(
            status_code=422,
            detail=cleaned_result.get("error", "Failed to process dataset structure.")
        )

    saved_metadata = save_cleaned_dataset(
        filename=file.filename,
        cleaned_data=cleaned_result,
        file_size_bytes=len(content_bytes)
    )

    return UploadResponse(
        success=True,
        dataset_id=saved_metadata["dataset_id"],
        filename=saved_metadata["filename"],
        rows_detected=saved_metadata["rows_detected"],
        rows_accepted=saved_metadata["rows_accepted"],
        rows_rejected=saved_metadata["rows_rejected"],
        columns_detected=saved_metadata["columns_detected"],
        columns_mapped=saved_metadata["columns_mapped"],
        columns_ignored=saved_metadata["columns_ignored"],
        duplicates_removed=saved_metadata["duplicates_removed"],
        missing_values_handled=saved_metadata["missing_values_handled"],
        start_date=saved_metadata["start_date"],
        end_date=saved_metadata["end_date"],
        stations_detected=saved_metadata["stations_detected"],
        merge_status=saved_metadata["merge_status"],
        message="Dataset processed and integrated into unified historical repository."
    )


@router.get("/data/status", response_model=MdmStatus)
def get_data_status():
    """Returns dataset status, station counts, date range and upload history."""
    return get_mdm_status()


@router.get("/data/aggregate", response_model=PeriodAggregationResponse)
def get_data_aggregate(
    station: Optional[str] = Query(None),
    period: str = Query("monthly", description="weekly, monthly, yearly, range, or daily"),
    anchor_date: Optional[str] = Query(None, description="Anchor reference date YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date for range filtering"),
    end_date: Optional[str] = Query(None, description="End date for range filtering")
):
    """
    Computes deterministic aggregations for Weekly, Monthly, Yearly, and Range periods
    directly from actual stored SQLite records without synthetic data.
    """
    return aggregate_mdm_period(
        station=station,
        period=period,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date
    )


@router.delete("/data/clear")

def clear_data():
    """Clears all uploaded MDM records and datasets for clean demo reset."""
    clear_mdm_data()
    return {"success": True, "message": "All MDM datasets cleared successfully."}


@router.get("/analytics/overview", response_model=OverviewAnalytics)
def get_overview_analytics(
    station: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Returns management-level overview answering the 5 core operational questions."""
    status = get_mdm_status()
    if not status.has_data:
        return OverviewAnalytics(
            has_data=False,
            dataset_status=status,
            energy_summary={},
            equipment_summary={},
            resource_risk_summary={},
            ai_management_insights=[]
        )

    energy = calculate_energy_analytics(station, start_date, end_date)
    equipment = calculate_equipment_health_analytics(station, start_date, end_date)
    resource = calculate_station_resource_risk(station, start_date, end_date)

    ai_insights = AIAnalysisService.generate_management_insights(
        energy.model_dump() if hasattr(energy, "model_dump") else energy.dict(),
        equipment.model_dump() if hasattr(equipment, "model_dump") else equipment.dict(),
        resource.model_dump() if hasattr(resource, "model_dump") else resource.dict()
    )

    dynamic_insights = AIAnalysisService.generate_dynamic_insights(
        energy.model_dump() if hasattr(energy, "model_dump") else energy.dict(),
        equipment.model_dump() if hasattr(equipment, "model_dump") else equipment.dict(),
        resource.model_dump() if hasattr(resource, "model_dump") else resource.dict(),
        status
    )

    return OverviewAnalytics(
        has_data=True,
        dataset_status=status,
        energy_summary={
            "total_energy": energy.total_energy_kwh,
            "unit": energy.total_energy_unit,
            "avg_power_kw": energy.avg_power_kw,
            "peak_demand_kw": energy.peak_demand_kw,
            "min_demand_kw": energy.min_demand_kw,
            "trend_direction": energy.trend_direction,
            "trend_pct": energy.trend_pct
        },
        equipment_summary={
            "records_analyzed": equipment.records_analyzed,
            "anomalies_detected": equipment.anomalies_detected,
            "high_risk_signals_count": equipment.high_risk_signals_count,
            "overall_risk_level": equipment.overall_risk_level,
            "most_affected_equipment": equipment.equipment_records[0].equipment_id if equipment.equipment_records else "None",
            "primary_signal": equipment.equipment_records[0].main_signal if equipment.equipment_records else "Nominal"
        },
        resource_risk_summary={
            "stations_analyzed": resource.stations_analyzed,
            "high_risk_stations_count": resource.high_risk_stations_count,
            "moderate_risk_stations_count": resource.moderate_risk_stations_count,
            "overall_network_risk": resource.overall_network_risk,
            "highest_risk_station": resource.station_risks[0].station if resource.station_risks else "None",
            "primary_driver": resource.station_risks[0].main_driver if resource.station_risks else "Nominal"
        },
        ai_management_insights=ai_insights,
        dynamic_ai_insights=dynamic_insights
    )


@router.get("/analytics/energy", response_model=EnergyAnalytics)
def get_energy_analytics_endpoint(
    station: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Calculates detailed energy consumption analytics."""
    res = calculate_energy_analytics(station, start_date, end_date)
    if res.has_data:
        # Generate module-specific AI insight
        insights = AIAnalysisService.generate_management_insights(
            res.dict(), {}, {}
        )
        res.ai_insights = {"findings": insights}
    return res


@router.get("/analytics/operator-insight", response_model=OperatorInsightResponse)
def get_operator_insight_endpoint(
    station: Optional[str] = Query(None, description="Station name (e.g. Bharati, Maitri, Dakshin Gangotri)"),
    anchor_date: Optional[str] = Query(None, description="Anchor reference date"),
    start_date: Optional[str] = Query(None, description="Start date filter"),
    end_date: Optional[str] = Query(None, description="End date filter"),
    horizon: int = Query(24, ge=1, le=168, description="Forecast horizon in hours (12, 24, 48)")
):
    """
    Connected Energy Intelligence & Operator Insight endpoint.
    Synthesizes Historical Energy Trend -> ML Forecast -> Operational Consequence -> Action.
    """
    return generate_operator_insight(
        station=station,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
        horizon=horizon
    )


@router.post("/analytics/operator-insight", response_model=OperatorInsightResponse)
def post_operator_insight_endpoint(payload: dict):
    """POST variant for connected operator insight."""
    station = payload.get("station")
    anchor_date = payload.get("anchor_date")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    horizon = int(payload.get("horizon", payload.get("forecast_horizon", 24)))
    policy = payload.get("policy")
    return generate_operator_insight(
        station=station,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
        horizon=horizon,
        policy_override=policy
    )


@router.get("/analytics/energy-reserve", response_model=EnergyReserveAnalytics)
def get_energy_reserve_endpoint(
    station: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    safe_days: float = Query(30.0),
    watch_days: float = Query(15.0),
    conserve_days: float = Query(7.0),
    critical_days: float = Query(3.0),
    configured_capacity_kwh: Optional[float] = Query(None)
):
    """
    Computes energy reserve duration, depletion scenarios across 4 operational modes,
    sustainability status, and 4-tier load allocation.
    """
    policy = {
        "safe_days": safe_days,
        "watch_days": watch_days,
        "conserve_days": conserve_days,
        "critical_days": critical_days,
        "configured_capacity_kwh": configured_capacity_kwh
    }
    return calculate_energy_reserve_analytics(
        station=station,
        start_date=start_date,
        end_date=end_date,
        policy_override=policy
    )


@router.post("/analytics/energy-reserve", response_model=EnergyReserveAnalytics)
def post_energy_reserve_endpoint(payload: dict):
    """POST variant for energy reserve analytics with custom simulation policy."""
    station = payload.get("station")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    policy = payload.get("policy", {})
    return calculate_energy_reserve_analytics(
        station=station,
        start_date=start_date,
        end_date=end_date,
        policy_override=policy
    )


@router.get("/analytics/energy-reserve/ai", response_model=EnergyReserveAIResponse)
def get_energy_reserve_ai_endpoint(
    station: Optional[str] = Query(None, description="Station name (e.g. Bharati, Maitri, Dakshin Gangotri)"),
    anchor_date: Optional[str] = Query(None, description="Anchor reference date"),
    horizon: int = Query(24, ge=1, le=168, description="Forecast horizon in hours (e.g. 12, 24, 48)")
):
    """
    Computes dynamic grounded AI operational decision-support for Antarctic station energy reserves.
    Separated from raw forecast queries to ensure modular, grounded explainability.
    """
    return get_energy_reserve_ai_analysis(
        station=station,
        anchor_date=anchor_date,
        horizon=horizon
    )


@router.post("/analytics/energy-reserve/ai", response_model=EnergyReserveAIResponse)
def post_energy_reserve_ai_endpoint(payload: dict):
    """POST variant for grounded energy reserve AI analysis."""
    station = payload.get("station")
    anchor_date = payload.get("anchor_date")
    horizon = int(payload.get("horizon", payload.get("forecast_horizon", 24)))
    policy = payload.get("policy")
    return get_energy_reserve_ai_analysis(
        station=station,
        anchor_date=anchor_date,
        horizon=horizon,
        policy_override=policy
    )


@router.get("/analytics/equipment-health", response_model=EquipmentHealthAnalytics)
def get_equipment_health_endpoint(
    station: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Performs equipment operational anomaly evaluation and risk profiling."""
    res = calculate_equipment_health_analytics(station, start_date, end_date)
    if res.has_data:
        insights = AIAnalysisService.generate_management_insights(
            {}, res.dict(), {}
        )
        res.ai_insights = {"findings": insights}
    return res


@router.get("/analytics/resource-risk", response_model=StationResourceRiskAnalytics)
def get_station_resource_risk_endpoint(
    station: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    anchor_date: Optional[str] = Query(None),
    horizon: int = Query(24)
):
    """Evaluates station resource risk across network stations with current and forecast horizon separation."""
    res = calculate_station_resource_risk(
        station=station,
        start_date=start_date,
        end_date=end_date,
        anchor_date=anchor_date,
        horizon=horizon
    )
    if res.has_data:
        insights = AIAnalysisService.generate_management_insights(
            {}, {}, res.dict()
        )
        res.ai_insights = {"findings": insights}
    return res


@router.post("/analytics/ai")
def perform_ai_analysis(payload: dict):
    """
    Direct endpoint to run focused AI analysis on data payload.
    Payload: {"analysis_type": "...", "data": {...}, "context": {...}}
    """
    analysis_type = payload.get("analysis_type", "general")
    data = payload.get("data", {})
    context = payload.get("context", {})
    return AIAnalysisService.analyze_dataset(data, analysis_type, context)


@router.post("/analytics/chat")
@router.post("/ai/chat")
def chat_with_analyst_endpoint(payload: dict):
    """
    AI Analyst Chat endpoint that understands current dashboard state and dataset.
    Payload: {
        "message": "...",
        "dashboard_context": {...},
        "history": [...]
    }
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Question message cannot be empty.")

    dashboard_context = payload.get("dashboard_context", {})
    history = payload.get("history", [])
    return AIAnalysisService.chat_with_analyst(
        message=message,
        dashboard_context=dashboard_context,
        conversation_history=history
    )


@router.get("/forecast/weather-load", response_model=WeatherLoadForecastResponse)
def get_weather_load_forecast_endpoint(
    station: Optional[str] = Query(None, description="Station name (e.g. Bharati, Maitri, Dakshin Gangotri)"),
    anchor_date: Optional[str] = Query(None, description="Anchor reference date/timestamp"),
    horizon: int = Query(24, ge=1, le=168, description="Forecast horizon in hours (e.g. 24)")
):
    """
    Computes a 24-hour ahead empirical weather load demand forecast using the
    pre-trained ML model (polar_ems_weather_load_forecaster.joblib) and generates
    grounded AI interpretations without numeric alteration.
    """
    return generate_weather_load_forecast(
        station=station,
        anchor_date=anchor_date,
        forecast_horizon=horizon
    )


@router.post("/forecast/weather-load", response_model=WeatherLoadForecastResponse)
def post_weather_load_forecast_endpoint(payload: dict):
    """POST variant for weather load forecasting."""
    station = payload.get("station")
    anchor_date = payload.get("anchor_date")
    horizon = int(payload.get("horizon", payload.get("forecast_horizon", 24)))
    return generate_weather_load_forecast(
        station=station,
        anchor_date=anchor_date,
        forecast_horizon=horizon
    )


