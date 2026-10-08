import React, { useEffect, useState, useCallback, useRef } from 'react'
import {
  getMdmStatus,
  getResourceRiskAnalytics,
  MdmStatus,
  StationResourceRiskAnalytics,
} from '../api'
import { MdmFilterBar } from '../components/MdmFilterBar'

interface MdmResourceRiskPageProps {
  onNavigate?: (page: string) => void
}

export const MdmResourceRiskPage: React.FC<MdmResourceRiskPageProps> = ({ onNavigate }) => {
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [data, setData] = useState<StationResourceRiskAnalytics | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedStation, setSelectedStation] = useState<string>('All')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [anchorDate, setAnchorDate] = useState<string>('')
  const [horizon, setHorizon] = useState<number>(24)

  const requestSeqRef = useRef<number>(0)

  const loadData = useCallback(async () => {
    requestSeqRef.current += 1
    const seq = requestSeqRef.current

    try {
      setLoading(true)
      setError(null)
      const st = await getMdmStatus()
      if (seq !== requestSeqRef.current) return
      setStatus(st)

      if (st.has_data) {
        if (!anchorDate && st.date_range_end) {
          setAnchorDate(st.date_range_end.slice(0, 10))
        }
        const res = await getResourceRiskAnalytics(
          selectedStation,
          startDate,
          endDate,
          anchorDate || (st.date_range_end ? st.date_range_end.slice(0, 10) : undefined),
          horizon
        )
        if (seq !== requestSeqRef.current) return
        setData(res)
      } else {
        setData(null)
      }
    } catch (err: any) {
      if (seq === requestSeqRef.current) {
        setError(err.message || 'Failed to load station resource risk')
      }
    } finally {
      if (seq === requestSeqRef.current) {
        setLoading(false)
      }
    }
  }, [selectedStation, startDate, endDate, anchorDate, horizon])

  useEffect(() => {
    loadData()
  }, [loadData])

  const renderRiskBadge = (risk?: string | null, isForecast: boolean = false) => {
    const r = (risk || (isForecast ? 'NORMAL' : 'LOW')).toUpperCase()
    let color = '#22c55e' // good green
    let label = r

    if (r === 'CRITICAL' || r === 'HIGH') {
      color = '#ef4444' // red
    } else if (r === 'CONSERVE' || r === 'MODERATE') {
      color = '#f97316' // amber/orange
    } else if (r === 'WATCH') {
      color = '#eab308' // yellow
    }

    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          fontSize: 10.5,
          fontWeight: 700,
          padding: '2px 8px',
          borderRadius: 12,
          textTransform: 'uppercase',
          letterSpacing: '0.4px',
          background: `${color}18`,
          color: color,
          border: `1px solid ${color}44`,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: color,
          }}
        />
        {label}
      </span>
    )
  }

  if (loading && !data && !status) {
    return (
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-dim)' }}>Evaluating cross-module resource risk matrix...</p>
      </div>
    )
  }

  if (!status || !status.has_data || !data || !data.has_data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
            Station Resource Risk Evaluation
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
            Empirical resource stress, battery reserve health and environmental exposure analysis
          </p>
        </div>

        <div className="card" style={{ padding: '64px 32px', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: 12 }}>
          <div style={{ fontSize: 40, marginBottom: 14 }}>🛡️</div>
          <h3 style={{ fontSize: 18, color: 'var(--text-main)', marginBottom: 8, fontWeight: 700 }}>
            No operational dataset available.
          </h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 13.5, maxWidth: 460, margin: '0 auto 20px auto', lineHeight: 1.5 }}>
            Upload CSV, XLS or XLSX to evaluate station-level battery reserve margins, energy availability risks, and environmental stress.
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

  const curNetRisk = data.network_current_risk || data.overall_network_risk || 'LOW'
  const fcNetRisk = data.network_forecast_risk || 'NORMAL'

  return (
    <div>
      {/* Top Header & Horizon Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 14, marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
            Station Resource Risk Evaluation
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
            Connected multi-station resource stress &amp; ML forecast-adjusted pressure analysis
          </p>
        </div>

        {/* Horizon Selector Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-secondary)', padding: '4px 8px', borderRadius: 8, border: '1px solid var(--border)' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Forecast Horizon:
          </span>
          {[12, 24, 48].map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              style={{
                background: horizon === h ? 'var(--accent)' : 'transparent',
                color: horizon === h ? '#ffffff' : 'var(--text-main)',
                border: 'none',
                borderRadius: 5,
                padding: '4px 10px',
                fontSize: 12,
                fontWeight: horizon === h ? 700 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {h}h
            </button>
          ))}
        </div>
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

      {/* Notice Banner */}
      {data.missing_fields_notice && data.missing_fields_notice.length > 0 && (
        <div style={{ padding: '8px 14px', background: 'var(--warn-dim)', border: '1px solid var(--warn)', borderRadius: 6, marginBottom: 16, fontSize: 12, color: 'var(--warn)' }}>
          <strong>Notice:</strong> {data.missing_fields_notice.join(' · ')}
        </div>
      )}

      {/* KPI Grid: Clearly separating Current vs Forecast-Adjusted Risk */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 20 }}>
        {/* Stations Analyzed */}
        <div className="card">
          <div className="kpi">
            <span className="label">Stations Analyzed</span>
            <span className="value">
              {data.stations_analyzed}
            </span>
            <span className="sub">{selectedStation !== 'All' ? selectedStation : 'Network wide'}</span>
          </div>
        </div>

        {/* Current Observed Risk */}
        <div className="card" style={{ borderLeft: '3px solid var(--accent)' }}>
          <div className="kpi">
            <span className="label">Current Resource Risk</span>
            <div style={{ marginTop: 6 }}>
              {renderRiskBadge(curNetRisk, false)}
            </div>
            <span className="sub" style={{ marginTop: 6 }}>Live observed telemetry</span>
          </div>
        </div>

        {/* Forecast-Adjusted Risk */}
        <div className="card" style={{ borderLeft: `3px solid ${fcNetRisk === 'CRITICAL' ? 'var(--bad)' : fcNetRisk === 'CONSERVE' ? 'var(--warn)' : 'var(--good)'}` }}>
          <div className="kpi">
            <span className="label">Forecast Resource Risk</span>
            <div style={{ marginTop: 6 }}>
              {renderRiskBadge(fcNetRisk, true)}
            </div>
            <span className="sub" style={{ marginTop: 6 }}>Next {horizon}h projected horizon</span>
          </div>
        </div>

        {/* High Risk Stations Count */}
        <div className="card">
          <div className="kpi">
            <span className="label">Stations Under Watch</span>
            <span className="value" style={{ color: (data.high_risk_stations_count + data.moderate_risk_stations_count) > 0 ? 'var(--warn)' : 'var(--good)' }}>
              {data.high_risk_stations_count + data.moderate_risk_stations_count}
            </span>
            <span className="sub">Immediate &amp; moderate focus</span>
          </div>
        </div>
      </div>

      {/* Forecast & Risk Relationship Banner */}
      {data.forecast_summary && (
        <div
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span style={{ fontSize: 18 }}>💡</span>
          <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-main)' }}>
            <strong style={{ color: 'var(--accent)' }}>Operational Risk Horizon Notice: </strong>
            {data.forecast_summary}
          </div>
        </div>
      )}

      {/* Station Risk Breakdown Table */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Connected Resource Risk &amp; Driver Matrix
          </h3>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {data.station_risks.length} evaluated resource factor{data.station_risks.length > 1 ? 's' : ''}
          </span>
        </div>

        {data.station_risks.length === 0 ? (
          <p style={{ color: 'var(--text-dim)', fontSize: 13, margin: 0 }}>
            No specific station resource stress factors identified.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Station</th>
                  <th>Resource Under Stress</th>
                  <th>Current Risk</th>
                  <th>Forecast Risk ({horizon}h)</th>
                  <th>Observed Driver / Forecast Reason</th>
                  <th>Telemetry Value</th>
                </tr>
              </thead>
              <tbody>
                {data.station_risks.map((item, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                      {item.station}
                    </td>
                    <td style={{ color: 'var(--text-main)', fontWeight: 500 }}>
                      {item.resource}
                    </td>
                    <td>
                      {renderRiskBadge(item.current_risk_level || item.risk_level, false)}
                    </td>
                    <td>
                      {renderRiskBadge(item.forecast_risk_level || item.risk_level, true)}
                    </td>
                    <td style={{ fontSize: 12, lineHeight: 1.4, color: 'var(--text-dim)', maxWidth: 360 }}>
                      <div>{item.main_driver}</div>
                      {item.forecast_driver_reason && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          ↳ <em>{item.forecast_driver_reason}</em>
                        </div>
                      )}
                    </td>
                    <td style={{ color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                      {item.current_value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Station Risk Comparison Cards */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ margin: '0 0 14px 0', fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
          Comparative Station Operational &amp; Forecast Baselines
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          {data.station_risk_comparison.map((st, i) => (
            <div
              key={i}
              style={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '14px 16px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)' }}>{st.station}</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {renderRiskBadge(st.current_risk || st.overall_risk, false)}
                  {st.forecast_risk && renderRiskBadge(st.forecast_risk, true)}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-dim)' }}>Current Electrical Demand:</span>
                  <span style={{ color: 'var(--text-main)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                    {st.current_energy_kw ?? st.recent_energy_kw ?? st.avg_energy_kw} kW
                  </span>
                </div>

                {st.forecast_peak_kw != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-dim)' }}>ML Forecast Peak ({horizon}h):</span>
                    <span style={{ color: '#fbbf24', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                      {st.forecast_peak_kw} kW
                    </span>
                  </div>
                )}

                {(st.current_battery_soc != null || st.battery_soc != null || st.recent_battery_soc != null) && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-dim)' }}>Battery Reserve SOC:</span>
                    <span
                      style={{
                        color: (st.current_battery_soc ?? st.battery_soc ?? st.recent_battery_soc ?? 0) < 35 ? 'var(--bad)' : 'var(--good)',
                        fontWeight: 600,
                        fontFamily: 'var(--mono)',
                      }}
                    >
                      {st.current_battery_soc ?? st.battery_soc ?? st.recent_battery_soc}%
                    </span>
                  </div>
                )}

                {st.renewable_share_pct != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-dim)' }}>Renewable Generation:</span>
                    <span style={{ color: 'var(--good)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                      {st.renewable_share_pct}%
                    </span>
                  </div>
                )}

                {st.temperature_c != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-dim)' }}>Mean Ambient Temp:</span>
                    <span style={{ color: 'var(--text-main)', fontFamily: 'var(--mono)' }}>{st.temperature_c}°C</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
