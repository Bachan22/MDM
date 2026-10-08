import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import {
  getMdmStatus,
  getOverviewAnalytics,
  getEnergyAnalytics,
  getEquipmentAnalytics,
  getResourceRiskAnalytics,
  getMdmAggregation,
  MdmStatus,
  OverviewAnalytics,
  EnergyAnalytics,
  EquipmentHealthAnalytics,
  StationResourceRiskAnalytics,
  PeriodAggregationResponse,
  AggregatedPoint,
} from '../api'
import { MdmFilterBar } from '../components/MdmFilterBar'
import { MdmReportModal } from '../components/MdmReportModal'

interface MdmOverviewPageProps {
  onNavigate: (page: string) => void
}

const MONTH_NAMES_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
]

const FULL_MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

function formatShortDate(dtStr: string): string {
  if (!dtStr || dtStr.length < 10) return dtStr || ''
  const parts = dtStr.slice(0, 10).split('-')
  if (parts.length < 3) return dtStr
  const mIdx = parseInt(parts[1], 10) - 1
  const day = parseInt(parts[2], 10)
  const month = MONTH_NAMES_SHORT[mIdx] || parts[1]
  return `${month} ${day}`
}

/**
 * Calculates the exact analytical start and end dates and human-readable period label
 * based on selectedDate (anchor), periodMode, and optional custom range.
 */
function computePeriodWindow(
  anchorStr: string,
  mode: 'weekly' | 'monthly' | 'yearly' | 'daily',
  customStart?: string,
  customEnd?: string
): { startDate: string; endDate: string; periodLabel: string } {
  if (mode === 'daily') {
    const s = customStart || anchorStr || '2025-08-01'
    const e = customEnd || anchorStr || '2025-08-16'
    const sLabel = formatShortDate(s)
    const eLabel = formatShortDate(e)
    return {
      startDate: s,
      endDate: e,
      periodLabel: s === e ? sLabel : `${sLabel} – ${eLabel}`,
    }
  }

  const parts = (anchorStr || '2025-08-15').slice(0, 10).split('-')
  const y = parseInt(parts[0], 10) || 2025
  const m = parseInt(parts[1], 10) || 8
  const d = parseInt(parts[2], 10) || 15

  if (mode === 'weekly') {
    // Construct UTC date to avoid timezone shift
    const dt = new Date(Date.UTC(y, m - 1, d))
    const dayOfWeek = dt.getUTCDay() // 0 = Sun, 1 = Mon ... 6 = Sat
    const diffToMon = (dayOfWeek + 6) % 7 // Mon = 0 ... Sun = 6

    const mon = new Date(Date.UTC(y, m - 1, d - diffToMon))
    const sun = new Date(Date.UTC(y, m - 1, d - diffToMon + 6))

    const startStr = mon.toISOString().slice(0, 10)
    const endStr = sun.toISOString().slice(0, 10)

    const sMonth = FULL_MONTH_NAMES[mon.getUTCMonth()]
    const eMonth = FULL_MONTH_NAMES[sun.getUTCMonth()]
    const sDay = mon.getUTCDate()
    const eDay = sun.getUTCDate()
    const sYear = mon.getUTCFullYear()
    const eYear = sun.getUTCFullYear()

    let label = ''
    if (sYear === eYear) {
      if (sMonth === eMonth) {
        label = `${sMonth.slice(0, 3)} ${sDay} – ${eDay}, ${sYear}`
      } else {
        label = `${sMonth.slice(0, 3)} ${sDay} – ${eMonth.slice(0, 3)} ${eDay}, ${sYear}`
      }
    } else {
      label = `${sMonth.slice(0, 3)} ${sDay}, ${sYear} – ${eMonth.slice(0, 3)} ${eDay}, ${eYear}`
    }
    return { startDate: startStr, endDate: endStr, periodLabel: label }
  }

  if (mode === 'monthly') {
    const daysInM = new Date(Date.UTC(y, m, 0)).getUTCDate()
    const startStr = `${y}-${String(m).padStart(2, '0')}-01`
    const endStr = `${y}-${String(m).padStart(2, '0')}-${String(daysInM).padStart(2, '0')}`
    const label = `${FULL_MONTH_NAMES[m - 1]} ${y}`
    return { startDate: startStr, endDate: endStr, periodLabel: label }
  }

  if (mode === 'yearly') {
    const startStr = `${y}-01-01`
    const endStr = `${y}-12-31`
    return { startDate: startStr, endDate: endStr, periodLabel: `${y}` }
  }

  return { startDate: anchorStr, endDate: anchorStr, periodLabel: anchorStr }
}

export const MdmOverviewPage: React.FC<MdmOverviewPageProps> = ({ onNavigate }) => {
  // ─── Core Dataset Status & Sub-Analytics State ─────────────────────────────
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [overview, setOverview] = useState<OverviewAnalytics | null>(null)
  const [energyData, setEnergyData] = useState<EnergyAnalytics | null>(null)
  const [equipmentData, setEquipmentData] = useState<EquipmentHealthAnalytics | null>(null)
  const [resourceData, setResourceData] = useState<StationResourceRiskAnalytics | null>(null)
  const [periodData, setPeriodData] = useState<PeriodAggregationResponse | null>(null)

  const [loading, setLoading] = useState<boolean>(true)
  const [periodLoading, setPeriodLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [showReportModal, setShowReportModal] = useState<boolean>(false)

  // ─── Single Source of Truth for Filtering & Date Context ───────────────────
  const [selectedStation, setSelectedStation] = useState<string>('All')
  const [selectedPeriod, setSelectedPeriod] = useState<'daily' | 'weekly' | 'monthly' | 'yearly'>('monthly')
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [customStartDate, setCustomStartDate] = useState<string>('')
  const [customEndDate, setCustomEndDate] = useState<string>('')

  // Calendar View State (Year and Month 1-12)
  const [calendarYear, setCalendarYear] = useState<number>(2025)
  const [calendarMonth, setCalendarMonth] = useState<number>(9) // 1 to 12

  // Chart interactivity & floating tooltip state
  const [activeBarIndex, setActiveBarIndex] = useState<number | null>(null)
  const [hoveredPoint, setHoveredPoint] = useState<AggregatedPoint | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const chartContainerRef = useRef<HTMLDivElement>(null)

  // Range dropdown menu toggle
  const [showRangeMenu, setShowRangeMenu] = useState<boolean>(false)

  // AI Quick Question
  const [quickQuestion, setQuickQuestion] = useState<string>('')

  // Sequence reference to discard out-of-order / stale asynchronous responses
  const requestSeqRef = useRef<number>(0)

  // Convenience mode flags
  const isYearly = selectedPeriod === 'yearly'
  const isMonthly = selectedPeriod === 'monthly'
  const isWeekly = selectedPeriod === 'weekly'

  // Compute active analytical window
  const activeWindow = useMemo(() => {
    return computePeriodWindow(selectedDate, selectedPeriod, customStartDate, customEndDate)
  }, [selectedDate, selectedPeriod, customStartDate, customEndDate])

  // ─── Initial Dataset Status Load ───────────────────────────────────────────
  const initDatasetStatus = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const st = await getMdmStatus()
      setStatus(st)

      if (st.has_data && st.date_range_end) {
        const dtStr = st.date_range_end.slice(0, 10)
        setSelectedDate((prev) => prev || dtStr)

        const pYear = parseInt(dtStr.slice(0, 4), 10)
        const pMonth = parseInt(dtStr.slice(5, 7), 10)
        if (!isNaN(pYear)) setCalendarYear(pYear)
        if (!isNaN(pMonth)) setCalendarMonth(pMonth)
      }
    } catch (err: any) {
      console.error('Failed to load dataset status:', err)
      setError(err.message || 'Failed to initialize dataset telemetry')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    initDatasetStatus()
  }, [initDatasetStatus])

  // ─── Main Recalculation Effect on Any Date/Period/Station Change ───────────
  useEffect(() => {
    if (!status || !status.has_data) return

    requestSeqRef.current += 1
    const seq = requestSeqRef.current
    setPeriodLoading(true)

    const fetchAllDashboardData = async () => {
      try {
        const { startDate: winStart, endDate: winEnd } = activeWindow

        // Concurrently run period aggregation and sub-analytics filtered by this window
        const [agg, ov, en, eq, rr] = await Promise.all([
          getMdmAggregation(
            selectedStation,
            selectedPeriod,
            selectedDate,
            selectedPeriod === 'daily' ? winStart : undefined,
            selectedPeriod === 'daily' ? winEnd : undefined
          ),
          getOverviewAnalytics(selectedStation, winStart, winEnd).catch(() => null),
          getEnergyAnalytics(selectedStation, winStart, winEnd).catch(() => null),
          getEquipmentAnalytics(selectedStation, winStart, winEnd).catch(() => null),
          getResourceRiskAnalytics(selectedStation, winStart, winEnd).catch(() => null),
        ])

        // Discard stale responses if user clicked another date in the meantime
        if (seq !== requestSeqRef.current) {
          return
        }

        setPeriodData(agg)
        if (ov) setOverview(ov)
        if (en) setEnergyData(en)
        if (eq) setEquipmentData(eq)
        if (rr) setResourceData(rr)
        setError(null)
      } catch (err: any) {
        if (seq === requestSeqRef.current) {
          console.error('Failed to update dashboard for selected date:', err)
          setError(err.message || 'Failed to update analysis for selected date')
        }
      } finally {
        if (seq === requestSeqRef.current) {
          setPeriodLoading(false)
        }
      }
    }

    fetchAllDashboardData()
  }, [status, selectedStation, selectedPeriod, selectedDate, customStartDate, customEndDate, activeWindow])

  // ─── Calendar Interaction Handlers ────────────────────────────────────────
  const handleSelectDay = (day: number) => {
    const formatted = `${calendarYear}-${String(calendarMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    setSelectedDate(formatted)
  }

  const handlePrevMonth = () => {
    if (selectedPeriod === 'yearly') {
      const newYear = calendarYear - 1
      setCalendarYear(newYear)
      const currentDay = selectedDate ? parseInt(selectedDate.slice(8, 10), 10) || 1 : 1
      const maxDaysInNewMonth = new Date(Date.UTC(newYear, calendarMonth, 0)).getUTCDate()
      const clampedDay = Math.min(currentDay, maxDaysInNewMonth)
      const newDate = `${newYear}-${String(calendarMonth).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`
      setSelectedDate(newDate)
    } else {
      let newMonth = calendarMonth - 1
      let newYear = calendarYear
      if (newMonth < 1) {
        newMonth = 12
        newYear -= 1
      }
      setCalendarYear(newYear)
      setCalendarMonth(newMonth)
      const currentDay = selectedDate ? parseInt(selectedDate.slice(8, 10), 10) || 1 : 1
      const maxDaysInNewMonth = new Date(Date.UTC(newYear, newMonth, 0)).getUTCDate()
      const clampedDay = Math.min(currentDay, maxDaysInNewMonth)
      const newDate = `${newYear}-${String(newMonth).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`
      setSelectedDate(newDate)
    }
  }

  const handleNextMonth = () => {
    if (selectedPeriod === 'yearly') {
      const newYear = calendarYear + 1
      setCalendarYear(newYear)
      const currentDay = selectedDate ? parseInt(selectedDate.slice(8, 10), 10) || 1 : 1
      const maxDaysInNewMonth = new Date(Date.UTC(newYear, calendarMonth, 0)).getUTCDate()
      const clampedDay = Math.min(currentDay, maxDaysInNewMonth)
      const newDate = `${newYear}-${String(calendarMonth).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`
      setSelectedDate(newDate)
    } else {
      let newMonth = calendarMonth + 1
      let newYear = calendarYear
      if (newMonth > 12) {
        newMonth = 1
        newYear += 1
      }
      setCalendarYear(newYear)
      setCalendarMonth(newMonth)
      const currentDay = selectedDate ? parseInt(selectedDate.slice(8, 10), 10) || 1 : 1
      const maxDaysInNewMonth = new Date(Date.UTC(newYear, newMonth, 0)).getUTCDate()
      const clampedDay = Math.min(currentDay, maxDaysInNewMonth)
      const newDate = `${newYear}-${String(newMonth).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`
      setSelectedDate(newDate)
    }
  }

  // Yearly month grid click
  const handleSelectYearlyMonth = (mNum: number) => {
    setCalendarMonth(mNum)
    const currentDay = selectedDate ? parseInt(selectedDate.slice(8, 10), 10) || 1 : 1
    const maxDays = new Date(Date.UTC(calendarYear, mNum, 0)).getUTCDate()
    const clampedDay = Math.min(currentDay, maxDays)
    const formatted = `${calendarYear}-${String(mNum).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`
    setSelectedDate(formatted)
    setSelectedPeriod('monthly')
  }

  // Chart Bar click
  const handleBarClick = (bar: AggregatedPoint) => {
    if (selectedPeriod === 'yearly') {
      if (!bar.key || bar.key.length < 7) return
      const yFromKey = parseInt(bar.key.slice(0, 4), 10)
      const mFromKey = parseInt(bar.key.slice(5, 7), 10)
      if (isNaN(yFromKey) || isNaN(mFromKey)) return
      setCalendarYear(yFromKey)
      setCalendarMonth(mFromKey)
      const currentDay = selectedDate ? parseInt(selectedDate.slice(8, 10), 10) || 1 : 1
      const maxDays = new Date(Date.UTC(yFromKey, mFromKey, 0)).getUTCDate()
      const clampedDay = Math.min(currentDay, maxDays)
      setSelectedDate(`${yFromKey}-${String(mFromKey).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`)
      setSelectedPeriod('monthly')
    } else if (bar.key && bar.key.length === 10) {
      setSelectedDate(bar.key)
      const pYear = parseInt(bar.key.slice(0, 4), 10)
      const pMonth = parseInt(bar.key.slice(5, 7), 10)
      if (!isNaN(pYear)) setCalendarYear(pYear)
      if (!isNaN(pMonth)) setCalendarMonth(pMonth)
    }
  }

  // Handle Range presets
  const handleRangeSelect = (preset: 'last7' | 'last30' | 'last90') => {
    setShowRangeMenu(false)
    setSelectedPeriod('daily')

    const baseDate = selectedDate ? new Date(selectedDate) : new Date()
    const days = preset === 'last7' ? 6 : preset === 'last30' ? 29 : 89
    const start = new Date(baseDate)
    start.setDate(start.getDate() - days)

    setCustomStartDate(start.toISOString().slice(0, 10))
    setCustomEndDate(baseDate.toISOString().slice(0, 10))
  }

  const handleAskQuickQuestion = (e: React.FormEvent) => {
    e.preventDefault()
    if (quickQuestion.trim()) {
      localStorage.setItem('polar_quick_question', quickQuestion)
      onNavigate('analyst')
    }
  }

  // ─── Guard: Initial Loading State ──────────────────────────────────────────
  if (loading && !overview && !status) {
    return (
      <div className="card" style={{ padding: 48, textAlign: 'center', margin: '20px 0' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>⚡</div>
        <p style={{ color: 'var(--text-dim)', fontSize: 14 }}>Loading management analytics &amp; telemetry...</p>
      </div>
    )
  }

  // ─── Guard: Empty Dataset State (Strict NO Fake Data) ───────────────────────
  if (!status || !status.has_data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ margin: '0 0 4px 0', fontSize: 22, fontWeight: 700, color: 'var(--text-main)' }}>
            Operations &amp; Analytics Overview
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
            Antarctic Research Station Operational Data Intelligence &amp; Multi-Resource Management
          </p>
        </div>

        <div
          className="card striped-pattern"
          style={{
            padding: '72px 32px',
            textAlign: 'center',
            border: '1px dashed var(--border)',
            borderRadius: 14,
          }}
        >
          <div style={{ fontSize: 44, marginBottom: 16 }}>📊</div>
          <h3 style={{ fontSize: 20, color: 'var(--text-main)', marginBottom: 8, fontWeight: 700 }}>
            No operational dataset available
          </h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 14, maxWidth: 500, margin: '0 auto 24px auto', lineHeight: 1.6 }}>
            Upload CSV, XLS or XLSX to begin analysis. The system will automatically clean telemetry, merge historical records, and compute energy, anomaly, and risk profiles.
          </p>
          <button
            className="btn btn-primary"
            onClick={() => onNavigate('upload')}
            style={{ padding: '10px 28px', fontSize: 13.5 }}
          >
            Upload Dataset →
          </button>
        </div>
      </div>
    )
  }

  // ─── Computed Values for the Active Period Window ──────────────────────────
  const es = overview?.energy_summary
  const eq = overview?.equipment_summary
  const rr = overview?.resource_risk_summary
  const insights = overview?.ai_management_insights || []

  // Dynamic Chart Bars from deterministic Period Aggregation API
  const chartBars: AggregatedPoint[] = periodData?.points || []
  const maxChartVal = Math.max(...chartBars.map((b) => b.value || 0), 10) * 1.25

  // Station Distribution Donut Chart Segments
  const stationComparison = resourceData?.station_risk_comparison || []
  const donutColors = ['#38bdf8', '#f59e0b', '#22c55e', '#ea580c', '#a855f7', '#ec4899']
  const donutData = (() => {
    if (stationComparison.length > 0) {
      const totalScore = stationComparison.reduce((acc, s) => acc + (s.avg_energy_kw || 1), 0) || 1
      return stationComparison.map((s, idx) => ({
        name: s.station,
        value: s.avg_energy_kw || 10,
        pct: Math.round(((s.avg_energy_kw || 1) / totalScore) * 100),
        color: donutColors[idx % donutColors.length],
      }))
    }
    if (status.stations.length > 0) {
      const pctEach = Math.round(100 / status.stations.length)
      return status.stations.map((stName, idx) => ({
        name: stName,
        value: Math.round((periodData?.current_total || es?.total_energy || 100) / status.stations.length),
        pct: pctEach,
        color: donutColors[idx % donutColors.length],
      }))
    }
    return [{ name: selectedStation !== 'All' ? selectedStation : 'Primary Station', value: periodData?.current_total || es?.total_energy || 100, pct: 100, color: '#38bdf8' }]
  })()

  // Recent Equipment & Telemetry Signals List
  const equipmentRecords = equipmentData?.equipment_records || []
  const anomalyTimeline = equipmentData?.anomaly_timeline || []
  const displayedEquipList = (() => {
    if (equipmentRecords.length > 0) {
      return equipmentRecords.slice(0, 4).map((r) => ({
        name: r.equipment_id,
        status: r.risk_level === 'HIGH' ? 'Critical' : r.risk_level === 'MODERATE' ? 'Pending' : 'Nominal',
        statusColor: r.risk_level === 'HIGH' ? 'red' : r.risk_level === 'MODERATE' ? 'amber' : 'green',
        dueText: r.last_observed ? r.last_observed.slice(5, 16) : 'Telemetry active',
        metric: r.current_load_kw ? `${r.current_load_kw.toFixed(1)} kW` : `${Math.max(20, 100 - (r.anomaly_count * 10))}% Health`,
      }))
    }
    if (anomalyTimeline.length > 0) {
      return anomalyTimeline.slice(0, 4).map((a) => ({
        name: a.equipment_id || a.station,
        status: 'Warning',
        statusColor: 'amber',
        dueText: a.timestamp.slice(5, 16),
        metric: a.metric_value ? `${a.metric_value} dev` : 'Anomaly',
      }))
    }
    return [
      { name: 'Unit A — Wind Turbine', status: 'Nominal', statusColor: 'green', dueText: 'Telemetry OK', metric: '96% Health' },
      { name: 'Unit B — Diesel Gen #1', status: 'Nominal', statusColor: 'green', dueText: 'Telemetry OK', metric: '91% Health' },
      { name: 'Unit C — Solar Inverter', status: 'Pending', statusColor: 'amber', dueText: 'Check scheduled', metric: '74% Health' },
    ]
  })()

  // Calculate Health Score
  const healthScore = Math.max(40, Math.min(100, 100 - ((eq?.anomalies_detected || 0) * 4)))

  // Calendar calculations for current calendarYear and calendarMonth
  const daysInMonth = new Date(calendarYear, calendarMonth, 0).getDate()
  // Monday is 0, Sunday is 6
  const firstDayOfWeek = (new Date(calendarYear, calendarMonth - 1, 1).getDay() + 6) % 7
  const availableDatesSet = new Set(periodData?.available_calendar_dates || [])

  // Check if selectedDate matches the displayed calendar month
  const isSelectedDateInCalendar = selectedDate.startsWith(`${calendarYear}-${String(calendarMonth).padStart(2, '0')}`)
  const selectedDayNum = isSelectedDateInCalendar ? parseInt(selectedDate.slice(8, 10), 10) : null

  // ─── Metric totals, KPIs and trend labels ──────────────────────────────────
  const displayTotalEnergy = periodData ? periodData.current_total : (es?.total_energy || 0)
  const displayTrendPct = periodData?.trend_pct != null ? Math.abs(periodData.trend_pct) : null
  const displayTrendDir = periodData?.trend_direction || (es?.trend_direction || 'Stable')

  // KPI values from deterministic backend aggregation
  const avgConsumptionValue = periodData?.avg_consumption ?? null
  const peakValue = periodData?.peak_value ?? null
  const peakPointLabel = periodData?.peak_label ?? null
  const lowestValue = periodData?.lowest_value ?? null
  const lowestPointLabel = periodData?.lowest_label ?? null
  const recordCount = periodData?.record_count ?? (es?.total_energy ? 1 : 0)

  // Period-adaptive labels
  const avgConsumptionLabel = isYearly ? 'Avg / Month' : 'Avg / Day'
  const peakLabel = isYearly ? 'Peak Month' : 'Peak Day'
  const lowestLabel = isYearly ? 'Lowest Month' : 'Lowest Day'

  // Trend comparison label
  const trendCompareLabel = isYearly
    ? `vs ${calendarYear - 1}`
    : isMonthly
    ? `vs ${MONTH_NAMES_SHORT[(calendarMonth - 2 + 12) % 12]}`
    : 'vs last period'

  // Header active period label
  const displayPeriodLabel = periodData?.period_label || activeWindow.periodLabel

  // Calendar header
  const calendarHeaderLabel = isYearly
    ? `${calendarYear}`
    : `${FULL_MONTH_NAMES[calendarMonth - 1]}, ${calendarYear}`

  // Y-axis ticks scaled to actual max
  const yAxisTicks = (() => {
    const step = maxChartVal / 4
    return [0, 1, 2, 3, 4].map((i) => Math.round(i * step))
  })()

  return (
    <div>
      {/* SVG Texture Pattern Definition */}
      <svg width="0" height="0" style={{ position: 'absolute', visibility: 'hidden' }}>
        <defs>
          <pattern id="diagonalHatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,255,255,0.06)" strokeWidth="2" />
          </pattern>
          <pattern id="diagonalHatchActive" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,255,255,0.18)" strokeWidth="2" />
          </pattern>
        </defs>
      </svg>

      {/* Dynamic Global Filter Bar */}
      <MdmFilterBar
        status={status}
        selectedStation={selectedStation}
        onStationChange={setSelectedStation}
        startDate={customStartDate}
        onStartDateChange={(d) => {
          setCustomStartDate(d)
          if (d) setSelectedPeriod('daily')
        }}
        endDate={customEndDate}
        onEndDateChange={(d) => {
          setCustomEndDate(d)
          if (d) setSelectedPeriod('daily')
        }}
        onRefresh={initDatasetStatus}
      />

      {/* Data Coverage & Quality Indicator Card (Overall Dataset Statistics) */}
      {status && status.has_data && (
        <div
          className="card"
          style={{
            padding: '14px 20px',
            marginBottom: 18,
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 18,
              }}
            >
              🛡️
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
                DATA COVERAGE &amp; QUALITY
              </div>
              <div style={{ fontSize: 13.5, fontWeight: 700, color: '#ffffff', marginTop: 2 }}>
                {status.records_count.toLocaleString()} Records across {status.stations_count} Station(s)
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 20, fontSize: 12 }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Date Range: </span>
              <strong style={{ color: '#ffffff' }}>
                {status.date_range_start?.slice(0, 10) || 'N/A'} → {status.date_range_end?.slice(0, 10) || 'N/A'}
              </strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Missing Values: </span>
              <strong style={{ color: status.missing_values_pct && status.missing_values_pct > 5 ? 'var(--warn)' : 'var(--text-main)' }}>
                {status.missing_values_pct ?? 0}%
              </strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Valid Records: </span>
              <strong style={{ color: '#ffffff' }}>
                {(status.valid_records_count || status.records_count).toLocaleString()}
              </strong>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--text-muted)' }}>Data Quality: </span>
              <span
                className={`badge ${(status.data_quality_pct ?? 100) >= 95 ? 'safe' : (status.data_quality_pct ?? 100) >= 85 ? 'warn' : 'critical'}`}
                style={{ fontSize: 11.5, padding: '3px 10px', fontWeight: 700 }}
              >
                {status.data_quality_pct ?? 100}%
              </span>
            </div>
          </div>

          <button
            className="btn"
            onClick={() => setShowReportModal(true)}
            style={{
              padding: '8px 18px',
              fontSize: 12.5,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: 'var(--accent, #38bdf8)',
              color: '#000000',
              fontWeight: 700,
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <span>📄</span>
            <span>Export Report</span>
          </button>
        </div>
      )}

      {error && (
        <div style={{ padding: '10px 14px', background: 'var(--bad-dim)', border: '1px solid var(--bad)', borderRadius: 8, marginBottom: 16, color: 'var(--bad)', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* ==========================================================================
          TOP TIER: Hero Energy Bar Chart (70%) + Interactive Calendar Widget (30%)
          ========================================================================== */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 18, marginBottom: 18 }}>
        
        {/* Left Card: Hero Energy Bar Chart */}
        <div className="card" style={{ padding: '22px 26px', display: 'flex', flexDirection: 'column', position: 'relative' }}>
          {/* Card Header & Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', letterSpacing: 0.4 }}>
                  Energy Consumption
                </span>
                {displayPeriodLabel && (
                  <span style={{ fontSize: 11, color: 'var(--accent)', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 8px', borderRadius: 10, fontWeight: 600 }}>
                    {displayPeriodLabel}
                  </span>
                )}
                {isYearly && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 6, fontWeight: 500 }}>
                    Monthly Aggregation
                  </span>
                )}
                {isMonthly && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 6, fontWeight: 500 }}>
                    Daily Aggregation
                  </span>
                )}
                {isWeekly && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 6, fontWeight: 500 }}>
                    7-Day Window
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 32, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff', letterSpacing: -0.8 }}>
                  {displayTotalEnergy.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 2 })}
                  <span style={{ fontSize: 14, color: 'var(--text-dim)', fontWeight: 500, marginLeft: 4 }}>
                    {es?.unit || 'kWh'}
                  </span>
                </span>

                {displayTrendPct != null ? (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      background: displayTrendDir === 'Increasing' ? 'rgba(245, 158, 11, 0.16)' : 'rgba(34, 197, 94, 0.16)',
                      color: displayTrendDir === 'Increasing' ? 'var(--warn)' : 'var(--good)',
                      padding: '3px 9px',
                      borderRadius: 14,
                      fontSize: 11.5,
                      fontWeight: 700,
                    }}
                  >
                    <span>{displayTrendDir === 'Increasing' ? '▲' : '▼'}</span>
                    <span>{displayTrendPct}%</span>
                    <span style={{ color: 'var(--text-dim)', fontWeight: 500, marginLeft: 2 }}>{trendCompareLabel}</span>
                  </span>
                ) : (
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '3px 8px', borderRadius: 10 }}>
                    No previous-period comparison
                  </span>
                )}

                {recordCount > 0 && (
                  <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 'auto' }}>
                    <strong>{recordCount.toLocaleString()}</strong> records
                  </span>
                )}
              </div>
            </div>

            {/* Pill Toggles: Weekly / Monthly / Yearly / Range */}
            <div style={{ position: 'relative' }}>
              <div className="pill-group">
                <button
                  className={`pill-btn ${selectedPeriod === 'weekly' ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedPeriod('weekly')
                    setShowRangeMenu(false)
                  }}
                >
                  Weekly
                </button>
                <button
                  className={`pill-btn ${selectedPeriod === 'monthly' ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedPeriod('monthly')
                    setShowRangeMenu(false)
                  }}
                >
                  Monthly
                </button>
                <button
                  className={`pill-btn ${selectedPeriod === 'yearly' ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedPeriod('yearly')
                    setShowRangeMenu(false)
                  }}
                >
                  Yearly
                </button>
                <button
                  className={`pill-btn ${selectedPeriod === 'daily' ? 'active' : ''}`}
                  onClick={() => setShowRangeMenu((prev) => !prev)}
                >
                  Range ▾
                </button>
              </div>

              {/* Range Dropdown Popup */}
              {showRangeMenu && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: 6,
                    background: 'var(--bg-popover, #111827)',
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    padding: '6px 0',
                    zIndex: 50,
                    boxShadow: '0 10px 28px rgba(0,0,0,0.6)',
                    minWidth: 150,
                  }}
                >
                  <div
                    style={{ padding: '7px 14px', fontSize: 12, color: 'var(--text-main)', cursor: 'pointer', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    onClick={() => handleRangeSelect('last7')}
                  >
                    Last 7 Days
                  </div>
                  <div
                    style={{ padding: '7px 14px', fontSize: 12, color: 'var(--text-main)', cursor: 'pointer', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    onClick={() => handleRangeSelect('last30')}
                  >
                    Last 30 Days
                  </div>
                  <div
                    style={{ padding: '7px 14px', fontSize: 12, color: 'var(--text-main)', cursor: 'pointer', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    onClick={() => handleRangeSelect('last90')}
                  >
                    Last 90 Days
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* SVG Hero Bar Chart */}
          <div ref={chartContainerRef} style={{ flex: 1, minHeight: 220, position: 'relative', marginTop: 10 }}>
            {periodLoading && (
              <div
                style={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  fontSize: 11,
                  color: 'var(--accent)',
                  background: 'rgba(15, 23, 42, 0.85)',
                  padding: '3px 8px',
                  borderRadius: 6,
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  zIndex: 10,
                }}
              >
                ↻ Updating analysis...
              </div>
            )}

            {chartBars.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-dim)' }}>
                <span style={{ fontSize: 24, marginBottom: 8 }}>📉</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>No telemetry available for this period</span>
                <span style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4 }}>
                  Select another date, station, or upload additional historical records.
                </span>
              </div>
            ) : (
              <svg
                width="100%"
                height="220"
                viewBox="0 0 680 220"
                preserveAspectRatio="none"
                onMouseLeave={() => {
                  setActiveBarIndex(null)
                  setHoveredPoint(null)
                }}
              >
                {/* Y-Axis Grid Lines & Ticks */}
                {yAxisTicks.map((tick, i) => {
                  const y = 180 - (i * 38)
                  return (
                    <g key={i}>
                      <line x1="36" y1={y} x2="680" y2={y} stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                      <text x="30" y={y + 4} fill="var(--text-muted)" fontSize="9" textAnchor="end" fontFamily="var(--mono)">
                        {tick >= 1000 ? `${(tick / 1000).toFixed(1)}k` : tick}
                      </text>
                    </g>
                  )
                })}

                {/* Bars */}
                {chartBars.map((bar, idx) => {
                  const count = chartBars.length
                  const barWidth = count <= 7 ? 56 : count <= 12 ? 38 : count <= 31 ? 14 : Math.max(6, Math.floor(580 / count) - 2)
                  const totalBarsWidth = count * barWidth
                  const gap = Math.max(2, (620 - totalBarsWidth) / (count + 1))
                  const x = 40 + idx * (barWidth + gap)
                  const barHeight = bar.value > 0 ? Math.max(12, (bar.value / maxChartVal) * 160) : 4
                  const y = 180 - barHeight
                  const isSelected = activeBarIndex === idx || (activeBarIndex === null && bar.is_peak)

                  // Strategic label visibility
                  let showLabel = true
                  if (isYearly) {
                    showLabel = true
                  } else if (count > 20) {
                    const keyParts = bar.key.split('-')
                    const dayNum = keyParts.length >= 3 ? parseInt(keyParts[2], 10) : idx + 1
                    showLabel = dayNum === 1 || dayNum % 5 === 0 || idx === count - 1 || isSelected
                  } else if (count > 10) {
                    showLabel = idx === 0 || idx === count - 1 || idx % 3 === 0 || isSelected
                  }

                  return (
                    <g
                      key={idx}
                      onMouseEnter={() => {
                        setActiveBarIndex(idx)
                        setHoveredPoint(bar)
                        if (chartContainerRef.current) {
                          const rect = chartContainerRef.current.getBoundingClientRect()
                          const relX = (x + barWidth / 2) / 680 * rect.width
                          const relY = (y / 220) * rect.height
                          setTooltipPos({ x: relX, y: relY })
                        }
                      }}
                      onClick={() => handleBarClick(bar)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* Bar Background Capsule */}
                      <rect
                        x={x}
                        y={y}
                        width={barWidth}
                        height={barHeight}
                        rx={barWidth > 20 ? 8 : 3}
                        ry={barWidth > 20 ? 8 : 3}
                        fill={
                          isSelected
                            ? '#38bdf8'
                            : bar.is_peak && bar.has_data
                            ? 'rgba(56,189,248,0.5)'
                            : bar.has_data
                            ? 'url(#diagonalHatch)'
                            : 'rgba(255,255,255,0.02)'
                        }
                        stroke={
                          isSelected
                            ? '#38bdf8'
                            : bar.is_peak && bar.has_data
                            ? 'rgba(56,189,248,0.7)'
                            : bar.has_data
                            ? 'rgba(255,255,255,0.12)'
                            : 'rgba(255,255,255,0.04)'
                        }
                        strokeWidth="1"
                        style={{ transition: 'all 0.15s ease' }}
                      />

                      {/* Top Cap Line */}
                      {bar.value > 0 && (
                        <line
                          x1={x + Math.max(2, barWidth * 0.15)}
                          y1={y + 3}
                          x2={x + barWidth - Math.max(2, barWidth * 0.15)}
                          y2={y + 3}
                          stroke={isSelected ? '#ffffff' : bar.is_peak ? 'rgba(56,189,248,0.9)' : 'rgba(255,255,255,0.5)'}
                          strokeWidth={barWidth > 20 ? 2 : 1.5}
                          strokeLinecap="round"
                        />
                      )}

                      {/* Peak marker */}
                      {bar.is_peak && bar.has_data && !isSelected && (
                        <text x={x + barWidth / 2} y={y - 4} fill="#38bdf8" fontSize="9" textAnchor="middle">★</text>
                      )}

                      {/* No-data indicator */}
                      {!bar.has_data && (
                        <text x={x + barWidth / 2} y={178} fill="rgba(255,255,255,0.18)" fontSize="7" textAnchor="middle">–</text>
                      )}

                      {/* X-Axis Label */}
                      {showLabel && (
                        <text
                          x={x + (barWidth / 2)}
                          y="212"
                          fill={isSelected ? '#ffffff' : bar.is_peak ? '#38bdf8' : 'var(--text-muted)'}
                          fontSize={count > 20 ? "8.5" : count > 12 ? "9.5" : "10.5"}
                          fontWeight={isSelected || bar.is_peak ? '700' : '500'}
                          textAnchor="middle"
                        >
                          {bar.label}
                        </text>
                      )}
                    </g>
                  )
                })}
              </svg>
            )}

            {/* Non-overlapping Floating Tooltip Card */}
            {hoveredPoint && (() => {
              const containerW = chartContainerRef.current?.clientWidth || 600
              const tooltipW = 175
              const clampedLeft = Math.max(tooltipW / 2 + 4, Math.min(tooltipPos.x, containerW - tooltipW / 2 - 4))
              const clampedTop = Math.max(10, tooltipPos.y - 12)
              return (
                <div
                  style={{
                    position: 'absolute',
                    left: clampedLeft,
                    top: clampedTop,
                    transform: 'translate(-50%, -100%)',
                    background: 'rgba(10, 12, 15, 0.96)',
                    border: '1px solid var(--border-hover)',
                    borderRadius: 8,
                    padding: '10px 13px',
                    pointerEvents: 'none',
                    zIndex: 30,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.7)',
                    whiteSpace: 'nowrap',
                    backdropFilter: 'blur(8px)',
                    minWidth: 145,
                  }}
                >
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 2 }}>
                    {hoveredPoint.full_date_label}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff', marginTop: 2 }}>
                    {hoveredPoint.has_data
                      ? hoveredPoint.value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 2 })
                      : 'No Data'}
                    {' '}
                    <span style={{ fontSize: 10.5, color: 'var(--text-dim)', fontWeight: 500 }}>
                      {hoveredPoint.has_data ? 'kWh' : ''}
                    </span>
                  </div>
                  {hoveredPoint.has_data && hoveredPoint.record_count > 0 && (
                    <div style={{ fontSize: 10.5, color: 'var(--text-dim)', marginTop: 3 }}>
                      {hoveredPoint.record_count.toLocaleString()} record{hoveredPoint.record_count > 1 ? 's' : ''}
                    </div>
                  )}
                  {!hoveredPoint.has_data && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, fontStyle: 'italic' }}>
                      No telemetry recorded
                    </div>
                  )}
                  {hoveredPoint.change_pct != null && (
                    <div
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        color: hoveredPoint.change_pct >= 0 ? 'var(--warn)' : 'var(--good)',
                        marginTop: 4,
                      }}
                    >
                      {hoveredPoint.change_pct >= 0 ? '▲ +' : '▼ '}
                      {Math.abs(hoveredPoint.change_pct)}%{' '}
                      <span style={{ color: 'var(--text-dim)', fontWeight: 500 }}>
                        vs {isYearly ? 'prior month' : 'prior day'}
                      </span>
                    </div>
                  )}
                  {isYearly && hoveredPoint.has_data && (
                    <div style={{ fontSize: 9, color: 'var(--accent)', marginTop: 5, fontStyle: 'italic' }}>
                      ↙ Click to drill down to month
                    </div>
                  )}
                  {isMonthly && hoveredPoint.has_data && (
                    <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 5, fontStyle: 'italic' }}>
                      ↙ Click to set active date
                    </div>
                  )}
                </div>
              )
            })()}
          </div>

          {/* KPI Strip below chart */}
          {periodData && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border-subtle)' }}>
              {/* Annual/Monthly/Period Total */}
              <div style={{ flex: '1 1 120px', minWidth: 100 }}>
                <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                  {isYearly ? 'Annual Total' : isMonthly ? 'Monthly Total' : 'Period Total'}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff', marginTop: 2 }}>
                  {displayTotalEnergy.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh
                </div>
              </div>
              {/* Avg */}
              {avgConsumptionValue != null && (
                <div style={{ flex: '1 1 120px', minWidth: 100 }}>
                  <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>{avgConsumptionLabel}</div>
                  <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff', marginTop: 2 }}>
                    {avgConsumptionValue.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh
                  </div>
                </div>
              )}
              {/* Peak */}
              {peakValue != null && (
                <div style={{ flex: '1 1 120px', minWidth: 100 }}>
                  <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>{peakLabel}</div>
                  <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', color: '#38bdf8', marginTop: 2 }}>
                    {peakValue.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh
                  </div>
                  {peakPointLabel && <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 1 }}>{peakPointLabel}</div>}
                </div>
              )}
              {/* Lowest */}
              {lowestValue != null && (
                <div style={{ flex: '1 1 120px', minWidth: 100 }}>
                  <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>{lowestLabel}</div>
                  <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--text-dim)', marginTop: 2 }}>
                    {lowestValue.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh
                  </div>
                  {lowestPointLabel && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>{lowestPointLabel}</div>}
                </div>
              )}
              {/* Records */}
              {recordCount > 0 && (
                <div style={{ flex: '1 1 100px', minWidth: 80 }}>
                  <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Records</div>
                  <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff', marginTop: 2 }}>
                    {recordCount.toLocaleString()}
                  </div>
                </div>
              )}
              {/* Trend */}
              <div style={{ flex: '1 1 120px', minWidth: 100 }}>
                <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Trend ({trendCompareLabel})</div>
                <div style={{ marginTop: 2 }}>
                  {displayTrendPct != null ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3,
                      background: displayTrendDir === 'Increasing' ? 'rgba(245,158,11,0.16)' : 'rgba(34,197,94,0.16)',
                      color: displayTrendDir === 'Increasing' ? 'var(--warn)' : 'var(--good)',
                      padding: '3px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700 }}>
                      {displayTrendDir === 'Increasing' ? '▲' : '▼'} {displayTrendPct}%
                    </span>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>No comparison</span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Card: Interactive Calendar Widget (Primary Analytical Controller) */}
        <div className="card calendar-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            {/* Calendar Header with Navigation */}
            <div className="calendar-header">
              <div
                className="calendar-nav-btn"
                onClick={handlePrevMonth}
                title={isYearly ? 'Previous Year' : 'Previous Month'}
              >
                ‹
              </div>
              <span style={{ fontSize: 13.5, fontWeight: 700, color: '#ffffff' }}>
                {calendarHeaderLabel}
              </span>
              <div
                className="calendar-nav-btn"
                onClick={handleNextMonth}
                title={isYearly ? 'Next Year' : 'Next Month'}
              >
                ›
              </div>
            </div>

            {/* Yearly Mode: month grid; Non-yearly: day grid */}
            {isYearly ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 5, padding: '8px 2px' }}>
                {MONTH_NAMES_SHORT.map((mName, mIdx) => {
                  const mNum = mIdx + 1
                  const ymKey = `${calendarYear}-${String(mNum).padStart(2, '0')}`
                  const hasData = chartBars.some((b) => b.key === ymKey && b.has_data)
                  const isPeak = chartBars.some((b) => b.key === ymKey && b.is_peak)
                  const isCurrentCalMonth = calendarMonth === mNum
                  return (
                    <div
                      key={mIdx}
                      onClick={() => handleSelectYearlyMonth(mNum)}
                      style={{
                        padding: '10px 4px',
                        textAlign: 'center',
                        fontSize: 12,
                        fontWeight: isCurrentCalMonth || isPeak ? 700 : 500,
                        color: isPeak ? '#38bdf8' : isCurrentCalMonth ? '#ffffff' : hasData ? 'var(--text-dim)' : 'var(--text-muted)',
                        background: isCurrentCalMonth
                          ? 'rgba(56, 189, 248, 0.18)'
                          : isPeak
                          ? 'rgba(56, 189, 248, 0.08)'
                          : hasData
                          ? 'var(--bg-secondary)'
                          : 'transparent',
                        border: isCurrentCalMonth
                          ? '1px solid rgba(56, 189, 248, 0.5)'
                          : hasData
                          ? '1px solid var(--border)'
                          : '1px solid transparent',
                        borderRadius: 8,
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                        opacity: hasData ? 1 : 0.4,
                      }}
                      title={hasData ? `${FULL_MONTH_NAMES[mIdx]} ${calendarYear}: click to inspect` : `No data for ${mName} ${calendarYear}`}
                    >
                      {mName}
                      {hasData && (
                        <div style={{ width: 4, height: 4, borderRadius: '50%', background: isPeak ? '#38bdf8' : 'var(--accent)', margin: '3px auto 0' }} />
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <>
                {/* Days of Week Headers */}
                <div className="calendar-grid" style={{ marginBottom: 6 }}>
                  {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
                    <div key={i} className="calendar-day-header">{d}</div>
                  ))}
                </div>

                {/* Calendar Cells */}
                <div className="calendar-grid">
                  {Array.from({ length: firstDayOfWeek }).map((_, i) => (
                    <div key={`fill-${i}`} className="calendar-cell striped" />
                  ))}

                  {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((day) => {
                    const dayStr = `${calendarYear}-${String(calendarMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                    const isActive = selectedDayNum === day
                    const hasTelemetry = availableDatesSet.has(dayStr)

                    // In weekly mode, highlight days in the active week window
                    const isInActiveWeek = isWeekly && dayStr >= activeWindow.startDate && dayStr <= activeWindow.endDate

                    return (
                      <div
                        key={day}
                        className={`calendar-cell ${isActive ? 'active' : ''}`}
                        onClick={() => handleSelectDay(day)}
                        style={{
                          position: 'relative',
                          border: isActive
                            ? '1px solid #38bdf8'
                            : isInActiveWeek
                            ? '1px solid rgba(56, 189, 248, 0.4)'
                            : hasTelemetry
                            ? '1px solid rgba(56, 189, 248, 0.25)'
                            : undefined,
                          background: isActive
                            ? '#38bdf8'
                            : isInActiveWeek
                            ? 'rgba(56, 189, 248, 0.12)'
                            : undefined,
                          color: isActive ? '#000000' : undefined,
                          fontWeight: isActive ? 800 : isInActiveWeek ? 700 : undefined,
                        }}
                        title={hasTelemetry ? `${dayStr}: Telemetry active. Click to analyze.` : `${dayStr}: Click to set date.`}
                      >
                        {day}
                        {hasTelemetry && !isActive && (
                          <span
                            style={{ position: 'absolute', bottom: 2, width: 3, height: 3, borderRadius: '50%', background: 'var(--accent)' }}
                          />
                        )}
                      </div>
                    )
                  })}

                  {Array.from({ length: (7 - ((firstDayOfWeek + daysInMonth) % 7)) % 7 }).map((_, i) => (
                    <div key={`trail-${i}`} className="calendar-cell striped" />
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Bottom Peak Load Metric Strip */}
          <div
            style={{
              marginTop: 16,
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16 }}>📊</span>
              <div>
                <div style={{ fontSize: 9.5, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                  {peakLabel}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff' }}>
                  {peakValue != null ? `${peakValue.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh` : 'No Data'}
                </div>
              </div>
            </div>
            {peakPointLabel && (
              <div style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600, textAlign: 'right' }}>
                {peakPointLabel}
              </div>
            )}
          </div>
        </div>

      </div>

      {/* ==========================================================================
          BOTTOM TIER: 3 Cards (AI Assistant + Distribution + Equipment Signals)
          ========================================================================== */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18, marginBottom: 18 }}>
        
        {/* Card 1: AI Assistant ("✨ How can I help you?") */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--accent)', fontSize: 16 }}>✨</span>
                <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#ffffff', textTransform: 'none' }}>
                  How can I help you?
                </h3>
              </div>
              <span
                onClick={() => onNavigate('analyst')}
                style={{ fontSize: 13, color: 'var(--text-dim)', cursor: 'pointer' }}
                title="Open full AI Analyst"
              >
                ↗
              </span>
            </div>

            {/* Dynamic AI Insights Warning Banner if fallback */}
            {overview?.dynamic_ai_insights?.status === 'fallback' && (
              <div
                style={{
                  padding: '6px 10px',
                  background: 'rgba(245, 158, 11, 0.12)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  borderRadius: 6,
                  fontSize: 11,
                  color: 'var(--warn)',
                  marginBottom: 10,
                }}
              >
                ⚠ AI Insights generated from empirical telemetry for active period.
              </div>
            )}

            {/* AI Summary Text */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
                Dynamic AI Insights ({displayPeriodLabel})
              </div>
              <p style={{ fontSize: 12.5, color: 'var(--text-dim)', lineHeight: 1.55, margin: 0 }}>
                {overview?.dynamic_ai_insights?.summary ||
                  insights[0]?.finding ||
                  (periodData?.has_data
                    ? `Station telemetry activity for ${displayPeriodLabel} shows total consumption of ${displayTotalEnergy.toLocaleString(undefined, { maximumFractionDigits: 1 })} kWh with peak demand of ${peakValue != null ? peakValue.toLocaleString() : 'N/A'} kWh.`
                    : 'No telemetry recorded for this specific period window. Select another date or period to inspect historical records.')}
                <span
                  onClick={() => onNavigate('analyst')}
                  style={{ color: 'var(--accent)', cursor: 'pointer', marginLeft: 4, fontWeight: 600 }}
                >
                  Read more
                </span>
              </p>
            </div>

            {/* Mini Metric Chips */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 12px' }}>
                <div style={{ fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 600 }}>Energy Trend</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                  <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff' }}>
                    {displayTrendPct != null ? `${displayTrendPct}%` : '0%'}
                  </span>
                  <span className={`badge ${displayTrendDir === 'Increasing' ? 'warn' : 'safe'}`} style={{ fontSize: 9.5, padding: '2px 6px' }}>
                    {displayTrendDir}
                  </span>
                </div>
              </div>

              <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 12px' }}>
                <div style={{ fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 600 }}>Anomalies</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                  <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff' }}>
                    {eq?.anomalies_detected != null ? eq.anomalies_detected : '0'}
                  </span>
                  <span className="badge safe" style={{ fontSize: 9.5, padding: '2px 6px' }}>
                    Processed
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Query Input Box */}
          <form onSubmit={handleAskQuickQuestion} style={{ position: 'relative' }}>
            <input
              type="text"
              placeholder="Ask me anything..."
              value={quickQuestion}
              onChange={(e) => setQuickQuestion(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 20,
                padding: '9px 38px 9px 14px',
                fontSize: 12.5,
                color: '#ffffff',
              }}
            />
            <button
              type="submit"
              style={{
                position: 'absolute',
                right: 6,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'transparent',
                border: 'none',
                color: 'var(--text-dim)',
                cursor: 'pointer',
                fontSize: 14,
                padding: 4,
              }}
            >
              ➤
            </button>
          </form>
        </div>

        {/* Card 2: Resource & Station Distribution (Donut Chart) */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#ffffff', textTransform: 'none' }}>
                Station Distribution
              </h3>
              <div className="pill-group" style={{ padding: '2px 8px', fontSize: 11 }}>
                <span>{displayPeriodLabel}</span>
              </div>
            </div>

            {/* Donut Chart with Center Total */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', gap: 14, margin: '8px 0' }}>
              <div style={{ position: 'relative', width: 130, height: 130 }}>
                <svg width="130" height="130" viewBox="0 0 100 100">
                  {/* Background Track Circle */}
                  <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="11" />
                  
                  {/* Colored Segments */}
                  {donutData.map((d, idx) => {
                    const strokeDash = `${(d.pct / 100) * 238} 238`
                    let prevOffset = 0
                    for (let i = 0; i < idx; i++) {
                      prevOffset += (donutData[i].pct / 100) * 360
                    }
                    return (
                      <circle
                        key={idx}
                        cx="50"
                        cy="50"
                        r="38"
                        fill="none"
                        stroke={d.color}
                        strokeWidth="11"
                        strokeDasharray={strokeDash}
                        transform={`rotate(${prevOffset - 90} 50 50)`}
                        strokeLinecap="round"
                      />
                    )
                  })}
                </svg>

                {/* Center Value */}
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                  }}
                >
                  <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff' }}>
                    {displayTotalEnergy ? `${Math.round(displayTotalEnergy).toLocaleString()}` : '0'}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    {isYearly ? 'Annual' : isMonthly ? 'Monthly' : 'Period'}
                  </span>
                </div>
              </div>

              {/* Legend Items */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11.5 }}>
                {donutData.slice(0, 5).map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
                    <span style={{ color: 'var(--text-dim)', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.name}
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: 10.5, marginLeft: 'auto' }}>
                      {item.pct}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom Callout Note */}
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 11.5,
              color: 'var(--text-dim)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
            }}
          >
            <span style={{ color: 'var(--accent)', fontSize: 12 }}>ℹ</span>
            <span>
              Primary consumption in {status.stations[0] || 'Main Station'} for {displayPeriodLabel}.
            </span>
          </div>
        </div>

        {/* Card 3: Equipment Health & Telemetry Anomalies */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#ffffff', textTransform: 'none' }}>
                Equipment &amp; Signals
              </h3>
              <div
                onClick={() => onNavigate('equipment')}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  fontSize: 13,
                  color: 'var(--text-dim)',
                }}
                title="View Equipment Matrix"
              >
                +
              </div>
            </div>

            {/* Health Score Segmented Meter Bar */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, fontSize: 11 }}>
                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Fleet Health Score ({displayPeriodLabel})</span>
                <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: '#ffffff' }}>{healthScore}</span>
              </div>
              <div className="segmented-meter">
                {Array.from({ length: 32 }, (_, i) => {
                  const activeCount = Math.round((healthScore / 100) * 32)
                  const isFilled = i < activeCount
                  return (
                    <div
                      key={i}
                      className={`meter-segment ${isFilled ? 'active-yellow' : ''}`}
                    />
                  )
                })}
              </div>
            </div>

            {/* Equipment Items List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {displayedEquipList.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: 12,
                    paddingBottom: 6,
                    borderBottom: idx < displayedEquipList.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  }}
                >
                  <div>
                    <div style={{ color: 'var(--text-main)', fontWeight: 600 }}>{item.name}</div>
                    <div style={{ color: 'var(--text-muted)', fontSize: 10.5 }}>{item.dueText}</div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 11,
                        color: item.statusColor === 'red' ? 'var(--bad)' : item.statusColor === 'amber' ? 'var(--warn)' : 'var(--good)',
                      }}
                    >
                      <span className={`dot ${item.statusColor}`} />
                      {item.status}
                    </span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: '#ffffff' }}>
                      {item.metric}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer Link */}
          <div
            onClick={() => onNavigate('equipment')}
            style={{
              marginTop: 12,
              paddingTop: 8,
              borderTop: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11.5,
              color: 'var(--text-dim)',
              cursor: 'pointer',
            }}
          >
            <span>View all equipment signals</span>
            <span>↗</span>
          </div>
        </div>

      </div>

      {/* ==========================================================================
          CROSS-SYSTEM RISK OVERVIEW STRIP (Period-Adaptive)
          ========================================================================== */}
      <div
        className="card"
        style={{
          padding: '14px 20px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 14,
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            SYSTEM RISK ({displayPeriodLabel}):
          </span>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          {/* Energy Risk */}
          <div
            onClick={() => onNavigate('energy')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 10px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
          >
            <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>Energy Risk:</span>
            <span className={`badge ${displayTrendDir === 'Increasing' ? 'warn' : 'safe'}`} style={{ fontSize: 10 }}>
              {displayTrendDir === 'Increasing' ? 'MODERATE' : 'LOW'}
            </span>
          </div>

          {/* Equipment Risk */}
          <div
            onClick={() => onNavigate('equipment')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 10px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
          >
            <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>Equipment Risk:</span>
            <span className={`badge ${eq?.overall_risk_level === 'HIGH' ? 'critical' : eq?.overall_risk_level === 'MODERATE' ? 'warn' : 'safe'}`} style={{ fontSize: 10 }}>
              {eq?.overall_risk_level || 'LOW'}
            </span>
          </div>

          {/* Resource Risk */}
          <div
            onClick={() => onNavigate('resource_risk')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 10px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
          >
            <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>Resource Risk:</span>
            <span className={`badge ${rr?.overall_network_risk === 'HIGH' ? 'critical' : rr?.overall_network_risk === 'MODERATE' ? 'warn' : 'safe'}`} style={{ fontSize: 10 }}>
              {rr?.overall_network_risk || 'LOW'}
            </span>
          </div>

          {/* Battery / Reserve Risk */}
          <div
            onClick={() => onNavigate('resource_risk')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 10px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
          >
            <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>Battery Risk:</span>
            <span className="badge safe" style={{ fontSize: 10 }}>
              NOMINAL
            </span>
          </div>
        </div>
      </div>

      {/* Dataset Provenance Footer */}
      <div className="card" style={{ padding: '12px 18px', background: 'var(--bg-secondary)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 12, fontSize: 11.5, color: 'var(--text-dim)' }}>
          <div>
            <strong style={{ color: 'var(--text-main)' }}>Active Dataset:</strong> {status.datasets_count} upload{status.datasets_count > 1 ? 's' : ''} ({status.records_count.toLocaleString()} cleaned observations)
          </div>
          <div>
            <strong style={{ color: 'var(--text-main)' }}>Temporal Span:</strong> {status.date_range_start?.slice(0, 10)} → {status.date_range_end?.slice(0, 10)}
          </div>
          <div>
            <strong style={{ color: 'var(--text-main)' }}>Active Stations:</strong> {status.stations.join(', ')}
          </div>
        </div>
      </div>

      {/* Export Analysis Report Modal */}
      <MdmReportModal
        isOpen={showReportModal}
        onClose={() => setShowReportModal(false)}
        status={status}
        overview={overview}
        selectedStation={selectedStation}
        periodMode={selectedPeriod}
        startDate={activeWindow.startDate}
        endDate={activeWindow.endDate}
      />
    </div>
  )
}
