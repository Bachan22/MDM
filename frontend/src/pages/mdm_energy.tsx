import React, { useEffect, useState } from 'react'
import { EnergyAnalytics, getEnergyAnalytics, getMdmStatus, MdmStatus } from '../api'
import { MdmFilterBar } from '../components/MdmFilterBar'

interface MdmEnergyPageProps {
  onNavigate?: (page: string) => void
}

export const MdmEnergyPage: React.FC<MdmEnergyPageProps> = ({ onNavigate }) => {
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [data, setData] = useState<EnergyAnalytics | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedStation, setSelectedStation] = useState<string>('All')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  // State for interactive tooltip on primary chart
  const [hoveredPoint, setHoveredPoint] = useState<{ x: number; y: number; timestamp: string; energy_kwh: number } | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const st = await getMdmStatus()
      setStatus(st)
      if (st.has_data) {
        const res = await getEnergyAnalytics(selectedStation, startDate, endDate)
        setData(res)
      } else {
        setData(null)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load energy analytics')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [selectedStation, startDate, endDate])

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
            Empirical demand profiling and load correlation from real station readings
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

  // Helper to render high-contrast SVG line chart with area gradient
  const renderTimeSeriesChart = (points: Array<{ timestamp: string; energy_kwh: number }>) => {
    if (!points || points.length === 0) return null
    const maxVal = Math.max(...points.map((p) => p.energy_kwh), 10)
    const minVal = Math.min(...points.map((p) => p.energy_kwh), 0)
    const range = maxVal - minVal || 1
    const width = 860
    const height = 240
    const paddingLeft = 50
    const paddingRight = 30
    const paddingTop = 25
    const paddingBottom = 35

    const plotWidth = width - paddingLeft - paddingRight
    const plotHeight = height - paddingTop - paddingBottom

    const coords = points.map((p, i) => {
      const x = paddingLeft + (i / (points.length - 1 || 1)) * plotWidth
      const y = paddingTop + plotHeight - ((p.energy_kwh - minVal) / range) * plotHeight
      return { x, y, point: p }
    })

    const pathD = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(' ')
    const areaD = `${pathD} L ${coords[coords.length - 1].x.toFixed(1)} ${(paddingTop + plotHeight).toFixed(1)} L ${coords[0].x.toFixed(1)} ${(paddingTop + plotHeight).toFixed(1)} Z`

    return (
      <div style={{ position: 'relative', width: '100%' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onMouseLeave={() => setHoveredPoint(null)}
        >
          <defs>
            <linearGradient id="energyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={paddingLeft} y1={paddingTop} x2={width - paddingRight} y2={paddingTop} stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
          <line x1={paddingLeft} y1={paddingTop + plotHeight * 0.5} x2={width - paddingRight} y2={paddingTop + plotHeight * 0.5} stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
          <line x1={paddingLeft} y1={paddingTop + plotHeight} x2={width - paddingRight} y2={paddingTop + plotHeight} stroke="rgba(255,255,255,0.12)" />

          {/* Area Fill */}
          <path d={areaD} fill="url(#energyGrad)" />

          {/* Line Path */}
          <path d={pathD} fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />

          {/* Interactive invisible hit targets */}
          {coords.map((c, idx) => (
            <circle
              key={idx}
              cx={c.x}
              cy={c.y}
              r={points.length < 40 ? 5 : 8}
              fill="transparent"
              style={{ cursor: 'crosshair' }}
              onMouseEnter={() =>
                setHoveredPoint({
                  x: (c.x / width) * 100,
                  y: (c.y / height) * 100,
                  timestamp: c.point.timestamp,
                  energy_kwh: c.point.energy_kwh,
                })
              }
            />
          ))}

          {/* Axis Labels */}
          <text x={paddingLeft - 8} y={paddingTop + 4} fill="var(--text-muted)" fontSize="10.5" textAnchor="end" fontFamily="var(--mono)">
            {maxVal.toFixed(0)} kW
          </text>
          <text x={paddingLeft - 8} y={paddingTop + plotHeight + 4} fill="var(--text-muted)" fontSize="10.5" textAnchor="end" fontFamily="var(--mono)">
            {minVal.toFixed(0)} kW
          </text>
          <text x={paddingLeft} y={height - 10} fill="var(--text-muted)" fontSize="10" fontFamily="var(--mono)">
            {points[0]?.timestamp.slice(0, 10)}
          </text>
          <text x={width - paddingRight} y={height - 10} fill="var(--text-muted)" fontSize="10" textAnchor="end" fontFamily="var(--mono)">
            {points[points.length - 1]?.timestamp.slice(0, 10)}
          </text>
        </svg>

        {/* Floating Tooltip */}
        {hoveredPoint && (
          <div
            className="chart-tooltip"
            style={{
              left: `${hoveredPoint.x}%`,
              top: `${hoveredPoint.y}%`,
            }}
          >
            <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginBottom: 2, fontFamily: 'var(--mono)' }}>
              {hoveredPoint.timestamp.slice(0, 16)}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="dot cyan" />
              <span style={{ fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 13 }}>
                {hoveredPoint.energy_kwh.toLocaleString()} kW
              </span>
            </div>
          </div>
        )}
      </div>
    )
  }

  // Render station breakdown bars
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
          Calculated from {data.time_series.length} sampled data points across {data.data_period.start?.slice(0, 10)} → {data.data_period.end?.slice(0, 10)}
        </p>
      </div>

      {/* Dynamic Global Filter Bar */}
      <MdmFilterBar
        status={status}
        selectedStation={selectedStation}
        onStationChange={setSelectedStation}
        startDate={startDate}
        onStartDateChange={setStartDate}
        endDate={endDate}
        onEndDateChange={setEndDate}
        onRefresh={loadData}
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
              {data.total_energy_kwh?.toLocaleString()} <span className="unit" style={{ color: 'var(--accent)' }}>{data.total_energy_unit}</span>
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

      {/* Large Primary Analytics Section: Full Width Hero Chart */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
              Primary Analysis · Continuous Demand Telemetry
            </h3>
            <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
              Empirical power draw across operational sampling intervals
            </span>
          </div>
          <span className="badge info" style={{ fontSize: 11 }}>
            Trend: {data.trend_direction} {data.trend_pct ? `(${data.trend_pct > 0 ? '+' : ''}${data.trend_pct}%)` : ''}
          </span>
        </div>
        {renderTimeSeriesChart(data.time_series)}
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
                Observed demand correlation with ambient temperature:
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
