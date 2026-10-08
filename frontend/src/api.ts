/** Minimal typed API client for the POLAR-EMS backend. */

const BASE = '/api'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export const get = <T,>(path: string) => req<T>(path)
export const post = <T,>(path: string, body?: unknown) =>
  req<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })

export interface ScenarioV1Response {
  scenario: string
  safe_operability_days: number
  cqrm_days: number
  risk_level: 'SAFE' | 'CAUTION' | 'CONSERVE' | 'CRITICAL' | string
  required_reserve_soc_pct: number
  optimizer_status: string
  safety_status: 'SAFE' | 'UNSAFE' | string
  final_decision: 'ACCEPT_PLAN' | 'REJECT_PLAN' | string
  operating_mode: 'NORMAL' | 'CONSERVATION' | string
  operator_intervention_required: boolean
  resupply_p10_days: number
  resupply_p50_days: number
  resupply_p90_days: number
  resupply_margin_days: number
  recommended_action: string
  reason: string
  violations: any[]
  initial_battery_soc_pct?: number
  final_battery_soc_pct?: number
  initial_fuel_l?: number
  final_fuel_l?: number
  fuel_used_l?: number
  generator_energy_kwh?: number
  renewable_used_kwh?: number
  renewable_curtailed_kwh?: number
  battery_discharge_kwh?: number
  battery_charge_kwh?: number
  first_violation?: { timestamp: string; violations: string[] }
  hourly_plan?: any[]
}

export const runScenarioV1 = (scenario: string, delayDays: number = 0.0) =>
  post<ScenarioV1Response>('/v1/scenario/run', { scenario, delay_days: delayDays })

// ---------------------------------------------------------------- types ----
export interface ResupplyDailyProb {
  day: number
  marginal_probability: number
  cumulative_arrival_probability: number
}

export interface ResupplyModel {
  scheduled_base_days: number
  slider_delay_days: number
  expected_days: number
  conservative_days: number
  optimistic_days: number
  confidence_level: number
  weather_delay_factor_days: number
  weather_impact: string
  primary_uncertainty: string
  daily_distribution: ResupplyDailyProb[]
  data_status: string
}

export interface Autonomy {
  safe_autonomy_days: number
  conservative_days: number
  expected_days: number
  optimistic_days: number
  confidence: number
  failure_probability_before_resupply: number
  next_resupply_days: number
  resupply_conservative_days?: number
  autonomy_margin_days: number
  cqrm_margin_days: number
  status: 'SAFE' | 'CAUTION' | 'CONSERVE' | 'CRITICAL' | string
  interpretation: string
  methodology: string
  assumptions: Record<string, unknown>
  resupply_model?: ResupplyModel
}

export interface BeforeAfterSnapshot {
  battery_kw: number
  diesel_kw: number
  flexible_load_pct: number
  reserve_soc_pct: number
}

export interface BeforeAfterReplan {
  has_changed: boolean
  trigger: string
  trigger_description: string
  before: BeforeAfterSnapshot
  after: BeforeAfterSnapshot
  reason: string
  result: string
  safe_operability_days: number
  margin_days: number
  shortfall_risk_pct: number
  timestamp: number
}

export interface WhatChanged {
  metric: string
  direction: 'up' | 'down' | 'neutral'
  detail: string
}

export interface DemoState {
  active: boolean
  step: number
  total_steps: number
  name: string
  badge?: string
  description?: string
  paused: boolean
}

export interface Station {
  station: { id: string; name: string; simulation: boolean }
  sim_time_h: number
  fuel_l: number
  fuel_pct: number
  battery_soc: number
  battery_soh: number
  battery_power_kw: number
  generator_running: boolean
  generator_output_kw: number
  generator_failed: boolean
  loads: { critical_kw: number; essential_kw: number; flexible_kw: number; total_kw: number; flexible_shed_pct: number }
  weather: { temperature_c: number; wind_speed_ms: number; solar_irradiance_wm2: number; condition: string }
  scenario: Record<string, boolean>
  connectivity: { internet: string; mqtt: string; cloud: string; sync_queue: number }
  mode: string
  mode_auto: boolean
  resupply: {
    in_days: number
    delay_days?: number
    expected_fuel_l: number
    model?: ResupplyModel
  }
  engines: Record<string, string>
  data_quality: { score: number; issues: string[] }
  balance: { solar_kw: number; wind_kw: number; battery_kw: number; diesel_kw: number; load_kw: number; heating_kw: number }
  autonomy: Autonomy
  latest_forecast: Forecast
  safety: SafetyResult
  awaiting_approval: boolean
  recommendation?: Recommendation
  recommendation_summary: string
  what_changed?: WhatChanged[]
  before_after_replan?: BeforeAfterReplan
  demo_state?: DemoState
}

export interface Step {
  start_offset_h: number
  hours: number
  diesel_kw: number
  battery_kw: number
  solar_kw: number
  wind_kw: number
  load_kw: number
  flexible_kw: number
  flexible_pct?: number
}

export interface SafetyResult {
  passed: boolean
  checks: { rule: string; passed: boolean; detail: string }[]
}

export interface Recommendation {
  trigger: string
  status: string
  plan: {
    horizon_h: number
    steps: Step[]
    expected_fuel_l: number
    fuel_consumed_6h_l: number
    fuel_remaining_end_l: number
    expected_end_soc: number
    method: string
    recommendation_summary: string
    reserve_soc_target?: number
    flexible_load_pct?: number
  }
  safety: SafetyResult
  autonomy: Autonomy
  explanations: { question: string; reason_lines: string[]; safety_impact?: string; expected_fuel_saving_l?: number; expected_fuel_use_l?: number }[]
  what_changed?: WhatChanged[]
  before_after_replan?: BeforeAfterReplan
  awaiting_approval: boolean
}

export interface Forecast {
  targets: Record<string, { steps: Record<string, { value: number; lo: number; hi: number }>; model: string }>
  generated_at: number
}

export interface Alert {
  id: number
  ts: number
  severity: string
  code: string
  title: string
  message: string
  acknowledged: number
  occurrences: number
}

export interface SysEvent { ts: number; source: string; event: string; detail: string; status: string }

export interface BaselineComparison {
  baseline: {
    method: string
    fuel_consumed_6h_l: number
    fuel_remaining_end_l: number
    end_soc: number
    renewable_utilised_kw_avg: number
    diesel_avg_kw: number
    critical_load_hours_met: number
    critical_load_hours_total: number
    safe_autonomy_days: number
    resupply_margin_days: number
  }
  polar_ems: {
    method: string
    fuel_consumed_6h_l: number
    fuel_remaining_end_l: number
    end_soc: number
    renewable_utilised_kw_avg: number
    diesel_avg_kw: number
    critical_load_hours_met: number
    critical_load_hours_total: number
    safe_autonomy_days: number
    resupply_margin_days: number
    safety_validated: boolean
  }
  delta: {
    fuel_saved_6h_l: number
    autonomy_gain_days: number
    end_soc_improvement_pct: number
    renewable_utilisation_improvement_kw: number
    early_warning_advantage_h: number
    early_warning_advantage_days: number
  }
  warning_lead_time: {
    baseline_first_warning_h: number
    polar_ems_first_warning_h: number
    baseline_first_warning_days: number
    polar_ems_first_warning_days: number
    early_warning_advantage_h: number
    early_warning_advantage_days: number
  }
  summary: string
}

// ---------------------------------------------------------------- MDM types ----
export interface DatasetMetadata {
  id: string
  filename: string
  upload_timestamp: number
  rows_detected: number
  rows_accepted: number
  rows_rejected: number
  columns_detected: string[]
  columns_mapped: Record<string, string>
  columns_ignored: string[]
  duplicates_removed: number
  missing_values_handled: number
  start_date?: string
  end_date?: string
  stations: string[]
  file_size_bytes: number
}

export interface UploadResponse {
  success: boolean
  dataset_id: string
  filename: string
  rows_detected: number
  rows_accepted: number
  rows_rejected: number
  columns_detected: string[]
  columns_mapped: Record<string, string>
  columns_ignored: string[]
  duplicates_removed: number
  missing_values_handled: number
  start_date?: string
  end_date?: string
  stations_detected: string[]
  merge_status: string
  message: string
}

export interface MdmStatus {
  has_data: boolean
  records_count: number
  stations_count: number
  stations: string[]
  date_range_start?: string
  date_range_end?: string
  datasets_count: number
  available_variables: string[]
  datasets: DatasetMetadata[]
  missing_values_count?: number
  missing_values_pct?: number
  data_quality_pct?: number
  valid_records_count?: number
  rows_detected_count?: number
  rows_rejected_count?: number
}

export interface EnergyAnalytics {
  has_data: boolean
  data_period: { start?: string; end?: string }
  total_energy_kwh?: number
  total_energy_unit: string
  avg_power_kw?: number
  peak_demand_kw?: number
  min_demand_kw?: number
  avg_equipment_load_kw?: number
  trend_direction?: string
  trend_pct?: number
  consumption_by_station: Record<string, number>
  time_series: Array<{
    timestamp: string
    energy_kwh: number
    station: string
    temperature_c?: number
    equipment_load_kw?: number
  }>
  temp_vs_energy: Array<{
    temperature_c: number
    energy_kwh: number
    station: string
  }>
  load_vs_energy: Array<{
    equipment_load_kw: number
    energy_kwh: number
    station: string
  }>
  renewable_vs_consumption?: Array<{
    timestamp: string
    consumption_kwh: number
    renewable_kwh: number
    solar_kwh: number
    wind_kwh: number
  }>
  renewable_available: boolean
  ai_insights?: { findings: any[] }
  missing_fields_notice: string[]
}

export interface EquipmentHealthRecord {
  equipment_id: string
  station: string
  risk_level: string
  main_signal: string
  anomaly_count: number
  last_observed: string
  operating_temp_c?: number
  current_load_kw?: number
}

export interface EquipmentHealthAnalytics {
  has_data: boolean
  records_analyzed: number
  anomalies_detected: number
  high_risk_signals_count: number
  overall_risk_level: string
  has_true_failure_labels: boolean
  methodology_note: string
  equipment_records: EquipmentHealthRecord[]
  anomaly_timeline: Array<{
    timestamp: string
    equipment_id: string
    station: string
    metric_value?: number
    temperature?: number
    reason: string
  }>
  load_trend: Array<{
    timestamp: string
    load_kw?: number
    station: string
  }>
  temp_vs_load: Array<{
    temperature_c?: number
    load_kw?: number
    station: string
  }>
  ai_insights?: { findings: any[] }
  missing_fields_notice: string[]
}

export interface StationResourceRiskItem {
  station: string
  resource: string
  risk_level: string
  current_risk_level?: string
  forecast_risk_level?: string | null
  main_driver: string
  forecast_driver_reason?: string | null
  current_value: string
  historical_average: string
  evidence_text: string
}

export interface StationResourceRiskAnalytics {
  has_data: boolean
  stations_analyzed: number
  high_risk_stations_count: number
  moderate_risk_stations_count: number
  low_risk_stations_count: number
  overall_network_risk: string
  network_current_risk?: string
  network_forecast_risk?: string | null
  forecast_horizon_hours?: number
  forecast_summary?: string | null
  station_risks: StationResourceRiskItem[]
  station_risk_comparison: Array<{
    station: string
    overall_risk: string
    current_risk?: string
    forecast_risk?: string
    risk_score?: number
    avg_energy_kw: number
    recent_energy_kw?: number
    current_energy_kw?: number
    forecast_peak_kw?: number
    forecast_avg_kw?: number
    avg_battery_soc?: number
    recent_battery_soc?: number
    current_battery_soc?: number
    battery_soc?: number
    renewable_share_pct?: number
    avg_temperature_c?: number
    temperature_c?: number
  }>
  battery_available: boolean
  renewable_available: boolean
  ai_insights?: { findings: any[] }
  missing_fields_notice: string[]
}

export interface OverviewAnalytics {
  has_data: boolean
  dataset_status: MdmStatus
  energy_summary: {
    total_energy?: number
    unit?: string
    avg_power_kw?: number
    peak_demand_kw?: number
    min_demand_kw?: number
    trend_direction?: string
    trend_pct?: number
  }
  equipment_summary: {
    records_analyzed?: number
    anomalies_detected?: number
    high_risk_signals_count?: number
    overall_risk_level?: string
    most_affected_equipment?: string
    primary_signal?: string
  }
  resource_risk_summary: {
    stations_analyzed?: number
    high_risk_stations_count?: number
    moderate_risk_stations_count?: number
    overall_network_risk?: string
    highest_risk_station?: string
    primary_driver?: string
  }
  ai_management_insights: Array<{
    category: string
    title: string
    finding: string
    risk_level: string
    primary_driver: string
    recommendation: string
    evidence: string
    source: string
  }>
  dynamic_ai_insights?: {
    status: string
    message?: string
    insights: string[]
    summary?: string
    source?: string
  }
}

// ---------------------------------------------------------------- MDM API calls ----
export async function uploadDatasetFile(file: File, sheetName?: string): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const qs = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : ''
  const res = await fetch(`${BASE}/data/upload${qs}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Upload error (${res.status}): ${text.slice(0, 200)}`)
  }
  return res.json()
}

export const uploadDatasetCsv = uploadDatasetFile

export function runAiAnalysis(analysisType: string, data: any, context?: any): Promise<any> {
  return post('/analytics/ai', {
    analysis_type: analysisType,
    data,
    context,
  })
}

export interface AiAnalystResponse {
  answer: string
  key_metrics: string[]
  evidence: string[]
  recommendations: string[]
  confidence: 'high' | 'medium' | 'low' | string
  data_limitations: string[]
  source?: string
}

export function askAiAnalyst(
  message: string,
  dashboardContext?: Record<string, any>,
  history?: Array<{ role: string; content: string }>
): Promise<AiAnalystResponse> {
  return post<AiAnalystResponse>('/analytics/chat', {
    message,
    dashboard_context: dashboardContext || {},
    history: history || [],
  })
}

export function getMdmStatus(): Promise<MdmStatus> {
  return get<MdmStatus>('/data/status')
}

export function clearMdmData(): Promise<{ success: boolean; message: string }> {
  return req<{ success: boolean; message: string }>('/data/clear', { method: 'DELETE' })
}

export function getOverviewAnalytics(station?: string, startDate?: string, endDate?: string): Promise<OverviewAnalytics> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<OverviewAnalytics>(`/analytics/overview${qs}`)
}

export function getEnergyAnalytics(station?: string, startDate?: string, endDate?: string): Promise<EnergyAnalytics> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<EnergyAnalytics>(`/analytics/energy${qs}`)
}

export function getEquipmentAnalytics(station?: string, startDate?: string, endDate?: string): Promise<EquipmentHealthAnalytics> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<EquipmentHealthAnalytics>(`/analytics/equipment-health${qs}`)
}

export function getResourceRiskAnalytics(
  station?: string,
  startDate?: string,
  endDate?: string,
  anchorDate?: string,
  horizon: number = 24
): Promise<StationResourceRiskAnalytics> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  if (anchorDate) params.append('anchor_date', anchorDate)
  if (horizon) params.append('horizon', String(horizon))
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<StationResourceRiskAnalytics>(`/analytics/resource-risk${qs}`)
}

export interface AggregatedPoint {
  key: string
  label: string
  full_date_label: string
  value: number
  record_count: number
  is_peak: boolean
  is_lowest: boolean
  has_data: boolean
  change_pct?: number | null
}

export interface PeriodAggregationResponse {
  has_data: boolean
  period: string
  period_label: string
  anchor_date: string
  current_total: number
  previous_total?: number | null
  trend_pct?: number | null
  trend_direction?: string | null
  avg_consumption?: number | null
  peak_value?: number | null
  peak_label?: string | null
  lowest_value?: number | null
  lowest_label?: string | null
  record_count: number
  points: AggregatedPoint[]
  available_calendar_dates: string[]
  missing_notice?: string | null
}

export function getMdmAggregation(
  station?: string,
  period: string = 'monthly',
  anchorDate?: string,
  startDate?: string,
  endDate?: string
): Promise<PeriodAggregationResponse> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (period) params.append('period', period)
  if (anchorDate) params.append('anchor_date', anchorDate)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<PeriodAggregationResponse>(`/data/aggregate${qs}`)
}

export interface WeatherLoadForecastPoint {
  timestamp: string
  predicted_load_kw: number
  temperature?: number | null
  wind_speed?: number | null
}

export interface HistoricalTelemetryPoint {
  timestamp: string
  actual_load_kw: number
  temperature?: number | null
  wind_speed?: number | null
}

export interface WeatherLoadForecastResponse {
  status: 'success' | 'insufficient_data' | 'empty_dataset' | string
  message?: string | null
  model: string
  station: string
  generated_at: string
  forecast_horizon_hours: number
  current_load_kw?: number | null
  predicted_peak_kw?: number | null
  predicted_average_kw?: number | null
  predicted_min_kw?: number | null
  peak_time?: string | null
  recent_load_avg_kw?: number | null
  recent_load_peak_kw?: number | null
  trend?: string | null
  records_available?: number | null
  records_required?: number | null
  historical_points: HistoricalTelemetryPoint[]
  forecast_points: WeatherLoadForecastPoint[]
  ai_interpretation?: {
    status?: string
    interpretation?: string
    main_drivers?: string[]
    management_insight?: string
    source?: string
  } | null
  model_status?: {
    model_name: string
    status: string
    model_type: string
    algorithm: string
    target: string
    forecast_horizon: string
    features_count: number
    features_list?: string[]
    test_metrics?: {
      MAE?: number
      RMSE?: number
      MAPE_percent?: number
      R2?: number
    }
    baseline_mae_improvement_percent?: number
  } | null
}

export function getWeatherLoadForecast(
  station?: string,
  anchorDate?: string,
  horizon: number = 24
): Promise<WeatherLoadForecastResponse> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (anchorDate) params.append('anchor_date', anchorDate)
  if (horizon) params.append('horizon', String(horizon))
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<WeatherLoadForecastResponse>(`/forecast/weather-load${qs}`)
}

export interface EnergyRiskWindow {
  window: string
  peak_kw?: number | null
  reason: string
  severity?: string
}

export interface EnergyChargingWindow {
  window: string
  action: string
  favorable_factors?: string[]
}

export interface EnergyReserveAIResponse {
  status: 'success' | 'fallback' | 'data_required' | string
  station: string
  forecast_horizon_hours: number
  anchor_date?: string | null
  energy_status: 'NORMAL' | 'WATCH' | 'CONSERVE' | 'CRITICAL' | string
  status_badge_color: string
  energy_situation: string
  forecast_impact: string
  reserve_recommendation: string
  critical_window?: EnergyRiskWindow | null
  charging_opportunity?: EnergyChargingWindow | null
  recommended_actions: string[]
  why: string
  evidence: {
    forecast_peak_kw?: number | null
    forecast_avg_kw?: number | null
    recent_avg_kw?: number | null
    current_load_kw?: number | null
    current_reserve_pct?: number | null
    estimated_days_remaining?: number | null
    renewable_contribution_pct?: number | null
    solar_status?: string | null
    wind_status?: string | null
    temperature_c?: number | null
    wind_speed_m_s?: number | null
  }
  signal_availability: Record<string, string>
  missing_data_notices: string[]
  source: string
}

export function getEnergyReserveAIAnalysis(
  station?: string,
  anchorDate?: string,
  horizon: number = 24
): Promise<EnergyReserveAIResponse> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (anchorDate) params.append('anchor_date', anchorDate)
  if (horizon) params.append('horizon', String(horizon))
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<EnergyReserveAIResponse>(`/analytics/energy-reserve/ai${qs}`)
}

export interface EnergyTrendAnalysis {
  has_data: boolean
  consumption_trend_pct?: number | null
  consumption_trend_direction: string
  average_demand_kw?: number | null
  peak_demand_kw?: number | null
  min_demand_kw?: number | null
  demand_stress_pct?: number | null
  highest_consuming_station?: string | null
  station_shares: Record<string, number>
  equipment_load_change_pct?: number | null
  equipment_association_note?: string | null
  trend_summary: string
}

export interface OperatorInsightResponse {
  status: 'success' | 'fallback' | 'data_required' | string
  station: string
  anchor_date?: string | null
  forecast_horizon_hours: number
  priority_level: number
  priority_title: string
  energy_status: 'NORMAL' | 'WATCH' | 'CONSERVE' | 'CRITICAL' | string
  trend_analysis: EnergyTrendAnalysis
  current_situation: string
  forecast_impact: string
  operational_consequence: string
  recommended_actions: string[]
  underlying_metrics: Record<string, any>
  signal_availability: Record<string, string>
  missing_data_notices: string[]
  source: string
}

export function getOperatorInsight(
  station?: string,
  anchorDate?: string,
  startDate?: string,
  endDate?: string,
  horizon: number = 24
): Promise<OperatorInsightResponse> {
  const params = new URLSearchParams()
  if (station && station !== 'All' && station !== 'All Stations') params.append('station', station)
  if (anchorDate) params.append('anchor_date', anchorDate)
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  if (horizon) params.append('horizon', String(horizon))
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<OperatorInsightResponse>(`/analytics/operator-insight${qs}`)
}





