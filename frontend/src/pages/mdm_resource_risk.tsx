import React, { useEffect, useState } from 'react'
import { getMdmStatus, getResourceRiskAnalytics, MdmStatus, StationResourceRiskAnalytics } from '../api'
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

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const st = await getMdmStatus()
      setStatus(st)
      if (st.has_data) {
        const res = await getResourceRiskAnalytics(selectedStation, startDate, endDate)
        setData(res)
      } else {
        setData(null)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load station resource risk')
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
        <p style={{ color: 'var(--text-dim)' }}>Evaluating station-level resource risk matrix...</p>
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

  return (
    <div>
      {/* Top Header */}
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
          Station Resource Risk Evaluation
        </h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
          Multi-station resource stress analysis based on uploaded operational history
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

      {/* Notice Banner */}
      {data.missing_fields_notice && data.missing_fields_notice.length > 0 && (
        <div style={{ padding: '8px 14px', background: 'var(--warn-dim)', border: '1px solid var(--warn)', borderRadius: 6, marginBottom: 16, fontSize: 12, color: 'var(--warn)' }}>
          <strong>Notice:</strong> {data.missing_fields_notice.join(' · ')}
        </div>
      )}

      {/* KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 20 }}>
        <div className="card">
          <div className="kpi">
            <span className="label">Stations Analyzed</span>
            <span className="value">
              {data.stations_analyzed}
            </span>
            <span className="sub">Active research bases</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">High-Risk Stations</span>
            <span className="value" style={{ color: data.high_risk_stations_count > 0 ? 'var(--bad)' : 'var(--good)' }}>
              {data.high_risk_stations_count}
            </span>
            <span className="sub">Immediate attention required</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Moderate-Risk Stations</span>
            <span className="value" style={{ color: data.moderate_risk_stations_count > 0 ? 'var(--warn)' : 'var(--good)' }}>
              {data.moderate_risk_stations_count}
            </span>
            <span className="sub">Under close observation</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Network Resource Risk</span>
            <div style={{ marginTop: 6 }}>
              <span className={`badge ${data.overall_network_risk === 'HIGH' ? 'critical' : data.overall_network_risk === 'MODERATE' ? 'warn' : 'safe'}`} style={{ fontSize: 12, padding: '4px 10px' }}>
                <span className={`dot ${data.overall_network_risk === 'HIGH' ? 'red' : data.overall_network_risk === 'MODERATE' ? 'amber' : 'green'}`} />
                {data.overall_network_risk} RISK
              </span>
            </div>
            <span className="sub" style={{ marginTop: 6 }}>Consolidated status tier</span>
          </div>
        </div>
      </div>

      {/* Station Risk Breakdown Table */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Station Resource Risk &amp; Driver Matrix
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
                  <th>Risk Level</th>
                  <th>Primary Driver</th>
                  <th>Recent Value</th>
                  <th>Baseline Average</th>
                </tr>
              </thead>
              <tbody>
                {data.station_risks.map((item, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                      {item.station}
                    </td>
                    <td style={{ color: 'var(--text-main)' }}>
                      {item.resource}
                    </td>
                    <td>
                      <span
                        className={`badge ${item.risk_level === 'HIGH' || item.risk_level === 'CRITICAL' ? 'critical' : item.risk_level === 'MODERATE' ? 'warn' : 'safe'}`}
                        style={{ fontSize: 10 }}
                      >
                        <span className={`dot ${item.risk_level === 'HIGH' || item.risk_level === 'CRITICAL' ? 'red' : item.risk_level === 'MODERATE' ? 'amber' : 'green'}`} />
                        {item.risk_level}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-dim)' }}>
                      {item.main_driver}
                    </td>
                    <td style={{ color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                      {item.current_value}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                      {item.historical_average}
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
          Comparative Station Operational Baselines
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
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
                <span
                  className={`badge ${st.overall_risk === 'HIGH' ? 'critical' : st.overall_risk === 'MODERATE' ? 'warn' : 'safe'}`}
                  style={{ fontSize: 9.5 }}
                >
                  <span className={`dot ${st.overall_risk === 'HIGH' ? 'red' : st.overall_risk === 'MODERATE' ? 'amber' : 'green'}`} />
                  {st.overall_risk} RISK
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-dim)' }}>Recent Power Demand:</span>
                  <span style={{ color: 'var(--text-main)', fontWeight: 600, fontFamily: 'var(--mono)' }}>{st.recent_energy_kw} kW (Avg {st.avg_energy_kw} kW)</span>
                </div>
                {st.recent_battery_soc != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-dim)' }}>Battery SOC Reserve:</span>
                    <span style={{ color: st.recent_battery_soc < 35 ? 'var(--bad)' : 'var(--good)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                      {st.recent_battery_soc}% (Avg {st.avg_battery_soc}%)
                    </span>
                  </div>
                )}
                {st.avg_temperature_c != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-dim)' }}>Mean Ambient Temp:</span>
                    <span style={{ color: 'var(--text-main)', fontFamily: 'var(--mono)' }}>{st.avg_temperature_c}°C</span>
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
