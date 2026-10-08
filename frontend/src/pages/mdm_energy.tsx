import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react'
import {
  EnergyAnalytics,
  getEnergyAnalytics,
  getMdmStatus,
  getMdmAggregation,
  getOperatorInsight,
  MdmStatus,
  OperatorInsightResponse,
  PeriodAggregationResponse,
  AggregatedPoint,
} from '../api'
import { MdmFilterBar } from '../components/MdmFilterBar'

interface MdmEnergyPageProps {
  onNavigate?: (page: string) => void
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

function fmtKw(val?: number | null): string {
  if (val === null || val === undefined || isNaN(val)) return '— kW'
  return `${val.toLocaleString(undefined, { maximumFractionDigits: 1 })} kW`
}

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
    const dt = new Date(Date.UTC(y, m - 1, d))
    const dayOfWeek = dt.getUTCDay()
    const diffToMon = (dayOfWeek + 6) % 7

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

export const MdmEnergyPage: React.FC<MdmEnergyPageProps> = ({ onNavigate }) => {
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [data, setData] = useState<EnergyAnalytics | null>(null)
  const [periodData, setPeriodData] = useState<PeriodAggregationResponse | null>(null)
  const [operatorInsight, setOperatorInsight] = useState<OperatorInsightResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [periodLoading, setPeriodLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const [selectedStation, setSelectedStation] = useState<string>('All')
  const [selectedPeriod, setSelectedPeriod] = useState<'weekly' | 'monthly' | 'yearly' | 'daily'>('weekly')
  const [anchorDate, setAnchorDate] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  // Interactivity state for the primary bar chart
  const [activeBarIndex, setActiveBarIndex] = useState<number | null>(null)
  const [hoveredPoint, setHoveredPoint] = useState<AggregatedPoint | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [showRangeMenu, setShowRangeMenu] = useState<boolean>(false)

  const requestSeqRef = useRef<number>(0)

  const isYearly = selectedPeriod === 'yearly'
  const isMonthly = selectedPeriod === 'monthly'
  const isWeekly = selectedPeriod === 'weekly'

  const activeWindow = useMemo(() => {
    return computePeriodWindow(anchorDate, selectedPeriod, startDate, endDate)
  }, [anchorDate, selectedPeriod, startDate, endDate])

  // Initial status load
  const initStatus = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const st = await getMdmStatus()
      setStatus(st)

      if (st.has_data && st.date_range_end) {
        const dtStr = st.date_range_end.slice(0, 10)
        setAnchorDate((prev) => prev || dtStr)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load energy analytics status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    initStatus()
  }, [initStatus])

  // Synchronized analytics + aggregation + operator insight fetch on any filter or period change
  useEffect(() => {
    if (!status || !status.has_data) return

    requestSeqRef.current += 1
    const seq = requestSeqRef.current
    setPeriodLoading(true)

    const fetchEnergyAnalytics = async () => {
      try {
        const { startDate: winStart, endDate: winEnd } = activeWindow

        const [enRes, aggRes, insightRes] = await Promise.all([
          getEnergyAnalytics(selectedStation, winStart, winEnd).catch(() => null),
          getMdmAggregation(
            selectedStation,
            selectedPeriod,
            anchorDate,
            selectedPeriod === 'daily' ? winStart : undefined,
            selectedPeriod === 'daily' ? winEnd : undefined
          ).catch(() => null),
          getOperatorInsight(
            selectedStation,
            anchorDate,
            winStart,
            winEnd,
            24
          ).catch((err) => {
            console.warn('Operator insight fetch error:', err)
            return null
          }),
        ])

        if (seq !== requestSeqRef.current) return

        if (enRes) setData(enRes)
        if (aggRes) setPeriodData(aggRes)
        if (insightRes) setOperatorInsight(insightRes)
        setError(null)
      } catch (err: any) {
        if (seq === requestSeqRef.current) {
          setError(err.message || 'Failed to calculate energy analytics')
        }
      } finally {
        if (seq === requestSeqRef.current) {
          setPeriodLoading(false)
        }
      }
    }
    fetchEnergyAnalytics()
  }, [status, selectedStation, selectedPeriod, anchorDate, startDate, endDate, activeWindow])

  const handleRangeSelect = (preset: 'last7' | 'last30' | 'last90') => {
    setShowRangeMenu(false)
    setSelectedPeriod('daily')

    const baseDate = anchorDate ? new Date(anchorDate) : new Date()
    const days = preset === 'last7' ? 6 : preset === 'last30' ? 29 : 89
    const start = new Date(baseDate)
    start.setDate(start.getDate() - days)

    setStartDate(start.toISOString().slice(0, 10))
    setEndDate(baseDate.toISOString().slice(0, 10))
  }

  // ─── Loading & Empty States ────────────────────────────────────────────────
  if (loading && !data && !status) {
    return (
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-dim)' }}>Loading energy consumption analytics...</p>
      </div>
    )
  }

  if (!status || !status.has_data || !data || !data.has_data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
            Energy Consumption Analysis
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
            Empirical demand profiling and equipment load association from real station readings
          </p>
        </div>

        <div className="card" style={{ padding: '64px 32px', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: 12 }}>
          <div style={{ fontSize: 40, marginBottom: 14 }}>⚡</div>
          <h3 style={{ fontSize: 18, color: 'var(--text-main)', marginBottom: 8, fontWeight: 700 }}>
            No operational dataset available.
          </h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 13.5, maxWidth: 460, margin: '0 auto 20px auto', lineHeight: 1.5 }}>
            Upload CSV, XLS or XLSX containing energy consumption or power demand telemetry to begin analysis.
          </p>
          {onNavigate && (
            <button
              className="btn btn-primary"
              onClick={() => onNavigate('upload')}
              style={{ padding: '10px 24px', fontSize: 13 }}
            >
              Upload Dataset →
            </button>
          )}
        </div>
      </div>
    )
  }

  // ─── Primary Aggregated Bar Chart Renderer ────────────────────────────────
  const chartBars: AggregatedPoint[] = periodData?.points || []
  const maxChartVal = Math.max(...chartBars.map((b) => b.value || 0), 10) * 1.25
  const displayPeriodLabel = periodData?.period_label || activeWindow.periodLabel

  const renderAggregatedBarChart = () => {
    if (chartBars.length === 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-dim)' }}>
          <span style={{ fontSize: 24, marginBottom: 8 }}>📉</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>No telemetry available for this period.</span>
          <span style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4 }}>
            Select another date or upload additional historical data.
          </span>
        </div>
      )
    }

    const width = 860
    const height = 230
    const paddingLeft = 55
    const paddingRight = 30
    const paddingTop = 32
    const paddingBottom = 35

    const plotWidth = width - paddingLeft - paddingRight
    const plotHeight = height - paddingTop - paddingBottom
    const count = chartBars.length

    // Responsive bar sizing
    const barWidth = count <= 7 ? 62 : count <= 12 ? 42 : count <= 31 ? 16 : Math.max(6, Math.floor(plotWidth / count) - 2)
    const totalBarsWidth = count * barWidth
    const gap = Math.max(2, (plotWidth - totalBarsWidth) / (count + 1))

    // Y-Axis Ticks
    const yStep = maxChartVal / 4
    const yTicks = [0, 1, 2, 3, 4].map((i) => Math.round(i * yStep))

    // Calculate bar coordinates & trend line points
    const barCoords = chartBars.map((bar, idx) => {
      const x = paddingLeft + gap + idx * (barWidth + gap)
      const barH = bar.value > 0 ? Math.max(10, (bar.value / maxChartVal) * plotHeight) : 4
      const y = paddingTop + plotHeight - barH
      const centerX = x + barWidth / 2
      const centerY = y
      return { x, y, barH, centerX, centerY, bar }
    })

    // Trend Polyline path (connecting bar tops)
    const validTrendPoints = barCoords.filter((c) => c.bar.has_data)
    const trendPath = validTrendPoints.length > 1
      ? `M ${validTrendPoints.map((pt) => `${pt.centerX.toFixed(1)},${pt.centerY.toFixed(1)}`).join(' L ')}`
      : ''

    return (
      <div ref={chartContainerRef} style={{ position: 'relative', width: '100%' }}>
        {periodLoading && (
          <div
            style={{
              position: 'absolute',
              top: -8,
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

        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onMouseLeave={() => {
            setActiveBarIndex(null)
            setHoveredPoint(null)
          }}
        >
          <defs>
            <pattern id="diagonalHatchEnergy" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,255,255,0.06)" strokeWidth="2" />
            </pattern>
          </defs>

          {/* Y-Axis Grid Lines & Labels */}
          {yTicks.map((tick, i) => {
            const y = paddingTop + plotHeight - (i * (plotHeight / 4))
            return (
              <g key={i}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke="rgba(255,255,255,0.04)"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <text
                  x={paddingLeft - 10}
                  y={y + 4}
                  fill="var(--text-muted)"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="var(--mono)"
                >
                  {tick >= 1000 ? `${(tick / 1000).toFixed(1)}k` : tick} kWh
                </text>
              </g>
            )
          })}

          {/* Vertical Bars */}
          {barCoords.map((c, idx) => {
            const { x, y, barH, bar } = c
            const isSelected = activeBarIndex === idx || (activeBarIndex === null && bar.is_peak)

            // Intelligent X-axis label filtering
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
                    const relX = (c.centerX / width) * rect.width
                    const relY = (y / height) * rect.height
                    setTooltipPos({ x: relX, y: relY })
                  }
                }}
                onClick={() => {
                  if (bar.key && bar.key.length === 10) {
                    setAnchorDate(bar.key)
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                {/* Bar Capsule */}
                <rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={barH}
                  rx={barWidth > 20 ? 6 : 3}
                  ry={barWidth > 20 ? 6 : 3}
                  fill={
                    isSelected
                      ? '#38bdf8'
                      : bar.is_peak && bar.has_data
                      ? 'rgba(56,189,248,0.5)'
                      : bar.has_data
                      ? 'url(#diagonalHatchEnergy)'
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
                    y1={y + 2}
                    x2={x + barWidth - Math.max(2, barWidth * 0.15)}
                    y2={y + 2}
                    stroke={isSelected ? '#ffffff' : bar.is_peak ? 'rgba(56,189,248,0.9)' : 'rgba(255,255,255,0.5)'}
                    strokeWidth={barWidth > 20 ? 2 : 1.5}
                    strokeLinecap="round"
                  />
                )}

                {/* Peak Indicator Callout on Highest Bar */}
                {bar.is_peak && bar.has_data && (
                  <g>
                    <text
                      x={c.centerX}
                      y={y - 8}
                      fill="#38bdf8"
                      fontSize="10"
                      fontWeight="700"
                      textAnchor="middle"
                      fontFamily="var(--mono)"
                    >
                      ★ Peak ({bar.value.toLocaleString(undefined, { maximumFractionDigits: 0 })} kWh)
                    </text>
                  </g>
                )}

                {/* X-Axis Label */}
                {showLabel && (
                  <text
                    x={c.centerX}
                    y={height - 12}
                    fill={isSelected ? '#ffffff' : bar.is_peak ? '#38bdf8' : 'var(--text-muted)'}
                    fontSize={count > 20 ? "9" : count > 12 ? "10" : "11"}
                    fontWeight={isSelected || bar.is_peak ? '700' : '500'}
                    textAnchor="middle"
                  >
                    {bar.label}
                  </text>
                )}
              </g>
            )
          })}

          {/* Subtle Thin Trend Line Connecting Bar Peaks (No Area Fill) */}
          {trendPath && (
            <path
              d={trendPath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="1.8"
              strokeDasharray="5 4"
              opacity="0.65"
              strokeLinecap="round"
            />
          )}

          {/* Trend Line Data Dots */}
          {validTrendPoints.map((pt, i) => (
            <circle
              key={`dot-${i}`}
              cx={pt.centerX}
              cy={pt.centerY}
              r="2.5"
              fill="#38bdf8"
              opacity="0.75"
            />
          ))}
        </svg>

        {/* Clean Non-Overlapping Floating Tooltip */}
        {hoveredPoint && (() => {
          const containerW = chartContainerRef.current?.clientWidth || 600
          const tooltipW = 180
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
                minWidth: 155,
              }}
            >
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 2 }}>
                {hoveredPoint.full_date_label}
              </div>
              <div style={{ fontSize: 13.5, fontWeight: 700, fontFamily: 'var(--mono)', color: '#ffffff', marginTop: 2 }}>
                {hoveredPoint.has_data
                  ? `${hoveredPoint.value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 2 })} kWh`
                  : 'No Data'}
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
            </div>
          )
        })()}
      </div>
    )
  }

  // Station breakdown bars
  const stationEntries = Object.entries(data.consumption_by_station || {})
  const maxStationVal = Math.max(...stationEntries.map(([_, v]) => v), 1)

  return (
    <div>
      {/* Top Header */}
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
          Energy Consumption Analysis
        </h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
          Deterministic demand profiling &amp; equipment load contribution across {displayPeriodLabel}
        </p>
      </div>

      {/* Dynamic Global Filter Bar */}
      <MdmFilterBar
        status={status}
        selectedStation={selectedStation}
        onStationChange={setSelectedStation}
        startDate={startDate}
        onStartDateChange={(d) => {
          setStartDate(d)
          if (d) setSelectedPeriod('daily')
        }}
        endDate={endDate}
        onEndDateChange={(d) => {
          setEndDate(d)
          if (d) setSelectedPeriod('daily')
        }}
        onRefresh={initStatus}
      />

      {error && (
        <div style={{ padding: '10px 14px', background: 'var(--bad-dim)', border: '1px solid var(--bad)', borderRadius: 6, marginBottom: 16, color: 'var(--bad)', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Missing Columns Alerts if any */}
      {data.missing_fields_notice && data.missing_fields_notice.length > 0 && (
        <div style={{ padding: '8px 14px', background: 'var(--warn-dim)', border: '1px solid var(--warn)', borderRadius: 6, marginBottom: 16, fontSize: 12, color: 'var(--warn)' }}>
          <strong>Notice:</strong> {data.missing_fields_notice.join(' · ')}
        </div>
      )}

      {/* Primary KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 20 }}>
        <div className="card">
          <div className="kpi">
            <span className="label">Total Energy</span>
            <span className="value">
              {(periodData ? periodData.current_total : data.total_energy_kwh)?.toLocaleString()}{' '}
              <span className="unit" style={{ color: 'var(--accent)' }}>kWh</span>
            </span>
            <span className="sub">Integrated period consumption</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Average Demand</span>
            <span className="value">
              {data.avg_power_kw} <span className="unit">kW</span>
            </span>
            <span className="sub">Mean continuous load</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Peak Demand</span>
            <span className="value" style={{ color: 'var(--warn)' }}>
              {data.peak_demand_kw} <span className="unit">kW</span>
            </span>
            <span className="sub">Observed maximum spike</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Minimum Demand</span>
            <span className="value">
              {data.min_demand_kw} <span className="unit">kW</span>
            </span>
            <span className="sub">Baseload floor power</span>
          </div>
        </div>

        {data.avg_equipment_load_kw != null && (
          <div className="card">
            <div className="kpi">
              <span className="label">Avg Equipment Load</span>
              <span className="value">
                {data.avg_equipment_load_kw} <span className="unit">kW</span>
              </span>
              <span className="sub">Active machinery draw</span>
            </div>
          </div>
        )}
      </div>

      {/* Primary Analytics Section: Clean Aggregated Bar Chart with Period Selector */}
      <div className="card" style={{ padding: '22px 26px', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
                Primary Analysis · Energy Consumption Trend
              </h3>
              {displayPeriodLabel && (
                <span style={{ fontSize: 11, color: 'var(--accent)', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 8px', borderRadius: 10, fontWeight: 600 }}>
                  {displayPeriodLabel}
                </span>
              )}
            </div>
            <span style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 2, display: 'block' }}>
              Aggregated {isYearly ? 'monthly' : 'daily'} energy consumption ({periodData?.current_total ? `${periodData.current_total.toLocaleString()} kWh total` : ''})
            </span>
          </div>

          {/* Period Mode Selector Pills */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="badge info" style={{ fontSize: 11 }}>
              Trend: {periodData?.trend_direction || data.trend_direction}{' '}
              {periodData?.trend_pct != null
                ? `(${periodData.trend_pct > 0 ? '+' : ''}${periodData.trend_pct}%)`
                : data.trend_pct
                ? `(${data.trend_pct > 0 ? '+' : ''}${data.trend_pct}%)`
                : ''}
            </span>

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
        </div>

        {renderAggregatedBarChart()}
      </div>

      {/* Connected Energy Intelligence Section: Energy Trend Analysis + Operator Insight */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16, marginBottom: 20 }}>
        {/* Section 1: ENERGY TREND ANALYSIS */}
        <div className="card" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>
                Energy Trend Analysis
              </h3>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '2px 9px',
                  borderRadius: 10,
                  background:
                    operatorInsight?.trend_analysis.consumption_trend_direction === 'Increasing'
                      ? 'rgba(234, 179, 8, 0.15)'
                      : operatorInsight?.trend_analysis.consumption_trend_direction === 'Decreasing'
                      ? 'rgba(34, 197, 94, 0.15)'
                      : 'rgba(56, 189, 248, 0.15)',
                  color:
                    operatorInsight?.trend_analysis.consumption_trend_direction === 'Increasing'
                      ? '#eab308'
                      : operatorInsight?.trend_analysis.consumption_trend_direction === 'Decreasing'
                      ? '#22c55e'
                      : '#38bdf8',
                  border: '1px solid currentColor',
                }}
              >
                ● {operatorInsight?.trend_analysis.consumption_trend_direction || data.trend_direction || 'Stable'}
              </span>
            </div>
            <span style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>
              Historical Telemetry Behavior
            </span>
          </div>

          {/* 4 Quantitative Telemetry Indicators */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            <div style={{ padding: '10px 12px', background: 'var(--bg-main)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2, textTransform: 'uppercase' }}>
                Consumption Trend
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: (operatorInsight?.trend_analysis.consumption_trend_pct || data.trend_pct || 0) >= 0 ? '#eab308' : '#22c55e' }}>
                {(operatorInsight?.trend_analysis.consumption_trend_pct || data.trend_pct || 0) >= 0 ? '▲ +' : '▼ '}
                {Math.abs(operatorInsight?.trend_analysis.consumption_trend_pct ?? data.trend_pct ?? 0).toFixed(1)}%
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>
                vs previous comparable period
              </div>
            </div>

            <div style={{ padding: '10px 12px', background: 'var(--bg-main)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2, textTransform: 'uppercase' }}>
                Demand Stress (Peak vs Avg)
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fbbf24' }}>
                +{operatorInsight?.trend_analysis.demand_stress_pct ?? ((data.peak_demand_kw && data.avg_power_kw) ? (((data.peak_demand_kw - data.avg_power_kw) / data.avg_power_kw) * 100).toFixed(1) : '0.0')}%
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>
                Peak: {fmtKw(data.peak_demand_kw)} (Avg: {fmtKw(data.avg_power_kw)})
              </div>
            </div>

            <div style={{ padding: '10px 12px', background: 'var(--bg-main)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2, textTransform: 'uppercase' }}>
                Highest Energy Station
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>
                {operatorInsight?.trend_analysis.highest_consuming_station || 'All Stations'}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>
                {operatorInsight?.trend_analysis.station_shares && operatorInsight.trend_analysis.highest_consuming_station
                  ? `${operatorInsight.trend_analysis.station_shares[operatorInsight.trend_analysis.highest_consuming_station] || 100}% of network consumption`
                  : 'Network contribution'}
              </div>
            </div>

            <div style={{ padding: '10px 12px', background: 'var(--bg-main)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2, textTransform: 'uppercase' }}>
                Equipment Load Association
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, color: (operatorInsight?.trend_analysis.equipment_load_change_pct || 0) > 0 ? '#38bdf8' : 'var(--text-main)' }}>
                {operatorInsight?.trend_analysis.equipment_load_change_pct != null
                  ? `${operatorInsight.trend_analysis.equipment_load_change_pct >= 0 ? '+' : ''}${operatorInsight.trend_analysis.equipment_load_change_pct}% Shift`
                  : fmtKw(data.avg_equipment_load_kw)}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>
                {data.avg_equipment_load_kw ? `Average draw ${fmtKw(data.avg_equipment_load_kw)}` : 'Observed draw'}
              </div>
            </div>
          </div>

          {/* Historical Narrative Summary */}
          <div style={{ padding: '12px 14px', background: 'var(--bg-main)', borderRadius: 8, border: '1px solid var(--border)', fontSize: 12.5, lineHeight: 1.55, color: 'var(--text-main)' }}>
            <div>
              <strong style={{ color: '#38bdf8' }}>Observed Dynamics: </strong>
              {operatorInsight?.trend_analysis.trend_summary ||
                `Energy consumption is ${data.trend_direction?.toLowerCase() || 'stable'} (${data.trend_pct || 0}%) across ${displayPeriodLabel}.`}
            </div>
            {operatorInsight?.trend_analysis.equipment_association_note && (
              <div style={{ marginTop: 6, color: 'var(--text-dim)' }}>
                ℹ {operatorInsight.trend_analysis.equipment_association_note}
              </div>
            )}
          </div>
        </div>

        {/* Section 2: OPERATOR INSIGHT (Connected Operational Intelligence) */}
        <div className="card" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>
                Operator Insight & Connected Action
              </h3>
              {operatorInsight?.energy_status && (() => {
                const st = operatorInsight.energy_status
                const color = st === 'CRITICAL' ? '#ef4444' : st === 'CONSERVE' ? '#f97316' : st === 'WATCH' ? '#eab308' : '#22c55e'
                return (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      padding: '3px 10px',
                      borderRadius: 12,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      background: `${color}22`,
                      color: color,
                      border: `1px solid ${color}66`,
                    }}
                  >
                    ● {st}
                  </span>
                )
              })()}
            </div>

            <span
              className="badge"
              style={{
                background: 'rgba(56, 189, 248, 0.12)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                padding: '3px 10px',
                borderRadius: 12,
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              ✨ {operatorInsight?.source || 'Connected Intelligence Engine'}
            </span>
          </div>

          {/* 3-Step Narrative Blocks */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ padding: '12px 14px', background: 'var(--bg-main)', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, lineHeight: 1.55, color: 'var(--text-main)' }}>
              <div style={{ marginBottom: 6 }}>
                <strong style={{ color: '#38bdf8' }}>Current Situation: </strong>
                {operatorInsight?.current_situation ||
                  `Energy demand is currently operating at an average of ${fmtKw(data.avg_power_kw)}.`}
              </div>
              <div style={{ marginBottom: 6 }}>
                <strong style={{ color: '#fbbf24' }}>Forecast Impact: </strong>
                {operatorInsight?.forecast_impact ||
                  'Weather-aware ML forecasting projects standard baseload demand for the upcoming period.'}
              </div>
              <div>
                <strong style={{ color: '#a855f7' }}>Operational Consequence: </strong>
                {operatorInsight?.operational_consequence ||
                  'Current reserve levels are adequate to support projected station operations under nominal dispatch.'}
              </div>
            </div>

            {/* Recommended Operator Actions (Numbered) */}
            <div>
              <div
                style={{
                  fontSize: 11.5,
                  fontWeight: 700,
                  color: 'var(--text-dim)',
                  marginBottom: 6,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                Recommended Operator Actions:
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: 'var(--text-main)', lineHeight: 1.6 }}>
                {(operatorInsight?.recommended_actions && operatorInsight.recommended_actions.length > 0
                  ? operatorInsight.recommended_actions
                  : [
                      'Maintain standard operating reserve buffer across all 4 load tiers.',
                      'Review high-load equipment before applying broader conservation measures.',
                      'Leverage off-peak generation windows to stabilize battery reserves.',
                    ]
                ).map((act, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>
                    {act}
                  </li>
                ))}
              </ul>
            </div>

            {/* Signal Availability & Transparency Note (if any missing notices exist) */}
            {operatorInsight?.missing_data_notices && operatorInsight.missing_data_notices.length > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 2 }}>
                ℹ {operatorInsight.missing_data_notices.join(' • ')}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Secondary Analysis Grid: Station Breakdown + Correlations */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 16, marginBottom: 20 }}>
        {/* Chart 2: Consumption by Station */}
        <div className="card">
          <h3 style={{ margin: '0 0 14px 0', fontSize: 13, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Consumption by Station
          </h3>
          {stationEntries.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>No station breakdown available.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {stationEntries.map(([st, val]) => (
                <div key={st}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
                    <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{st}</span>
                    <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{val.toLocaleString()} kWh</span>
                  </div>
                  <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        width: `${((val / maxStationVal) * 100).toFixed(1)}%`,
                        background: 'var(--accent)',
                        borderRadius: 3,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Temperature vs Energy Correlation */}
        <div className="card">
          <h3 style={{ margin: '0 0 12px 0', fontSize: 13, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Energy Demand vs Temperature
          </h3>
          {data.temp_vs_energy && data.temp_vs_energy.length > 0 ? (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 10 }}>
                Observed demand relationship with ambient temperature:
              </div>
              <div style={{ maxHeight: 180, overflowY: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Station</th>
                      <th>Temp (°C)</th>
                      <th>Demand (kW)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.temp_vs_energy.slice(0, 10).map((pt, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{pt.station}</td>
                        <td style={{ color: pt.temperature_c < -25 ? 'var(--bad)' : 'var(--text-main)', fontFamily: 'var(--mono)' }}>
                          {pt.temperature_c}°C
                        </td>
                        <td style={{ color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                          {pt.energy_kwh} kW
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)', fontSize: 12.5 }}>
              Temperature data unavailable in uploaded dataset.
            </div>
          )}
        </div>

        {/* Renewable vs Consumption */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: 13, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Renewable Generation vs Consumption
          </h3>
          {data.renewable_available && data.renewable_vs_consumption ? (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 10 }}>
                Solar/wind generation compared against gross demand:
              </div>
              <div style={{ maxHeight: 190, overflowY: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Demand (kW)</th>
                      <th>Renewable (kW)</th>
                      <th>Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.renewable_vs_consumption.slice(0, 12).map((pt, i) => {
                      const cov = pt.consumption_kwh > 0 ? Math.min(100, (pt.renewable_kwh / pt.consumption_kwh) * 100) : 0
                      return (
                        <tr key={i}>
                          <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{pt.timestamp.slice(0, 16)}</td>
                          <td style={{ fontFamily: 'var(--mono)' }}>{pt.consumption_kwh}</td>
                          <td style={{ color: 'var(--good)', fontWeight: 600, fontFamily: 'var(--mono)' }}>{pt.renewable_kwh}</td>
                          <td>
                            <span className={`badge ${cov > 50 ? 'safe' : 'warn'}`} style={{ fontSize: 10 }}>
                              {cov.toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ padding: '24px 16px', textAlign: 'center', background: 'var(--bg-secondary)', borderRadius: 6 }}>
              <div style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 2 }}>
                Renewable generation data unavailable.
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>
                No solar or wind columns detected in the current dataset.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
