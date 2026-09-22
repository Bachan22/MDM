import React, { useEffect, useState } from 'react'
import { EquipmentHealthAnalytics, getEquipmentAnalytics, getMdmStatus, MdmStatus } from '../api'
import { MdmFilterBar } from '../components/MdmFilterBar'

interface MdmEquipmentPageProps {
  onNavigate?: (page: string) => void
}

export const MdmEquipmentPage: React.FC<MdmEquipmentPageProps> = ({ onNavigate }) => {
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [data, setData] = useState<EquipmentHealthAnalytics | null>(null)
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
        const res = await getEquipmentAnalytics(selectedStation, startDate, endDate)
        setData(res)
      } else {
        setData(null)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load equipment health analytics')
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
        <p style={{ color: 'var(--text-dim)' }}>Analyzing equipment telemetry and statistical anomalies...</p>
      </div>
    )
  }

  if (!status || !status.has_data || !data || !data.has_data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
            Equipment Health &amp; Anomaly Detection
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
            Operational anomaly detection from real generator, plant load and thermal readings
          </p>
        </div>

        <div className="card" style={{ padding: '64px 32px', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: 12 }}>
          <div style={{ fontSize: 40, marginBottom: 14 }}>⚙️</div>
          <h3 style={{ fontSize: 18, color: 'var(--text-main)', marginBottom: 8, fontWeight: 700 }}>
            No operational dataset available.
          </h3>
          <p style={{ color: 'var(--text-dim)', fontSize: 13.5, maxWidth: 460, margin: '0 auto 20px auto', lineHeight: 1.5 }}>
            Upload CSV, XLS or XLSX with equipment load, power, or thermal telemetry to begin analysis.
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
          Equipment Health &amp; Anomaly Detection
        </h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
          Empirical anomaly detection across {data.records_analyzed.toLocaleString()} operational readings
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

      {/* KPI Summary Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 20 }}>
        <div className="card">
          <div className="kpi">
            <span className="label">Records Analyzed</span>
            <span className="value">
              {data.records_analyzed.toLocaleString()}
            </span>
            <span className="sub">Telemetry data points</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Anomalies Detected</span>
            <span className="value" style={{ color: data.anomalies_detected > 0 ? 'var(--warn)' : 'var(--good)' }}>
              {data.anomalies_detected}
            </span>
            <span className="sub">Deviations (z &gt; 2.2)</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">High-Risk Signals</span>
            <span className="value" style={{ color: data.high_risk_signals_count > 0 ? 'var(--bad)' : 'var(--good)' }}>
              {data.high_risk_signals_count}
            </span>
            <span className="sub">Critical unit alerts</span>
          </div>
        </div>

        <div className="card">
          <div className="kpi">
            <span className="label">Current Observed Risk</span>
            <div style={{ marginTop: 6 }}>
              <span className={`badge ${data.overall_risk_level === 'HIGH' ? 'critical' : data.overall_risk_level === 'MODERATE' ? 'warn' : 'safe'}`} style={{ fontSize: 12, padding: '4px 10px' }}>
                <span className={`dot ${data.overall_risk_level === 'HIGH' ? 'red' : data.overall_risk_level === 'MODERATE' ? 'amber' : 'green'}`} />
                {data.overall_risk_level} RISK
              </span>
            </div>
            <span className="sub" style={{ marginTop: 6 }}>Statistical risk tier</span>
          </div>
        </div>
      </div>

      {/* Equipment Risk Table */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Equipment Operational Health Matrix
          </h3>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {data.equipment_records.length} unit{data.equipment_records.length > 1 ? 's' : ''} monitored
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Equipment ID</th>
                <th>Station</th>
                <th>Observed Risk</th>
                <th>Primary Signal</th>
                <th style={{ textAlign: 'center' }}>Anomalies</th>
                <th>Avg Temp</th>
                <th>Last Load</th>
                <th>Last Observed</th>
              </tr>
            </thead>
            <tbody>
              {data.equipment_records.map((rec, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                    {rec.equipment_id}
                  </td>
                  <td style={{ color: 'var(--text-dim)' }}>{rec.station}</td>
                  <td>
                    <span
                      className={`badge ${rec.risk_level === 'HIGH' ? 'critical' : rec.risk_level === 'MODERATE' ? 'warn' : 'safe'}`}
                      style={{ fontSize: 10 }}
                    >
                      <span className={`dot ${rec.risk_level === 'HIGH' ? 'red' : rec.risk_level === 'MODERATE' ? 'amber' : 'green'}`} />
                      {rec.risk_level}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-main)' }}>{rec.main_signal}</td>
                  <td style={{ textAlign: 'center', fontWeight: 600, fontFamily: 'var(--mono)', color: rec.anomaly_count > 0 ? 'var(--warn)' : 'var(--text-dim)' }}>
                    {rec.anomaly_count}
                  </td>
                  <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
                    {rec.operating_temp_c != null ? `${rec.operating_temp_c}°C` : 'N/A'}
                  </td>
                  <td style={{ color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                    {rec.current_load_kw != null ? `${rec.current_load_kw} kW` : 'N/A'}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--mono)' }}>
                    {rec.last_observed.slice(0, 16)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Anomaly Timeline Log */}
      {data.anomaly_timeline && data.anomaly_timeline.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Detected Anomaly Timeline Events
          </h3>
          <div style={{ maxHeight: 200, overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Equipment</th>
                  <th>Station</th>
                  <th>Observed Signal Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.anomaly_timeline.map((anom, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{anom.timestamp}</td>
                    <td style={{ fontWeight: 600 }}>{anom.equipment_id}</td>
                    <td style={{ color: 'var(--text-dim)' }}>{anom.station}</td>
                    <td style={{ color: 'var(--warn)' }}>{anom.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Methodology & Limitations Note (Mandatory) */}
      <div className="card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 4 }}>
          Scientific Methodology &amp; Scope
        </div>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>
          {data.methodology_note}
        </p>
      </div>
    </div>
  )
}
