import React, { useEffect, useState } from 'react'
import { getMdmStatus, MdmStatus } from './api'

// MDM Page components
import { MdmOverviewPage } from './pages/mdm_overview'
import { MdmEnergyPage } from './pages/mdm_energy'
import { MdmForecastPage } from './pages/mdm_forecast'
import { MdmEquipmentPage } from './pages/mdm_equipment'
import { MdmResourceRiskPage } from './pages/mdm_resource_risk'
import { MdmAnalystPage } from './pages/mdm_analyst'
import { MdmUploadPage } from './pages/mdm_upload'
import { ErrorBoundary } from './components/ErrorBoundary'

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: '⌂', symbol: 'Overview' },
  { id: 'energy', label: 'Energy Analysis', icon: '⚡', symbol: 'Energy' },
  { id: 'forecast', label: 'Weather Load Forecast', icon: '📈', symbol: 'Forecast' },
  { id: 'equipment', label: 'Equipment Health', icon: '⚙', symbol: 'Equipment' },
  { id: 'resource_risk', label: 'Resource Risk', icon: '🛡', symbol: 'Resource Risk' },
  { id: 'analyst', label: 'AI Analyst', icon: '✨', symbol: 'AI Analyst' },
  { id: 'upload', label: 'Dataset Management', icon: '📁', symbol: 'Datasets' },
] as const

export type PageId = typeof NAV_ITEMS[number]['id']

export const App: React.FC = () => {
  const [page, setPage] = useState<string>(() => {
    return localStorage.getItem('polar_mdm_page') || 'overview'
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [mdmStatus, setMdmStatus] = useState<MdmStatus | null>(null)

  const refreshStatus = async () => {
    try {
      const st = await getMdmStatus()
      setMdmStatus(st)
    } catch (err) {
      console.error('Error fetching MDM status:', err)
    }
  }

  useEffect(() => {
    localStorage.setItem('polar_mdm_page', page)
  }, [page])

  useEffect(() => {
    refreshStatus()
    const interval = setInterval(refreshStatus, 8000)
    return () => clearInterval(interval)
  }, [])

  const pages: Record<string, React.ReactNode> = {
    overview: <MdmOverviewPage onNavigate={setPage} />,
    energy: <MdmEnergyPage onNavigate={setPage} />,
    forecast: <MdmForecastPage onNavigate={setPage} />,
    equipment: <MdmEquipmentPage onNavigate={setPage} />,
    resource_risk: <MdmResourceRiskPage onNavigate={setPage} />,
    analyst: <MdmAnalystPage onNavigate={setPage} />,
    upload: <MdmUploadPage onNavigate={setPage} onUploadSuccess={refreshStatus} />,
  }

  // Active page title map
  const pageTitles: Record<string, { title: string; subtitle: string }> = {
    overview: { title: 'Overview', subtitle: 'Station Operational Intelligence & Multi-Resource Matrix' },
    energy: { title: 'Energy Analytics', subtitle: 'Continuous Load Profiling, Spikes & Equipment Association' },
    forecast: { title: 'Weather Load Forecast', subtitle: 'Pre-Trained ML Load Demand Forecasting & Grounded AI Analysis' },
    equipment: { title: 'Equipment Health', subtitle: 'Statistical Anomaly Detection & Failure Risk Matrix' },
    resource_risk: { title: 'Resource Risk', subtitle: 'Battery Reserves, Consumables & Environmental Stress' },
    analyst: { title: 'AI Operational Analyst', subtitle: 'Empirical Query Assistant Backed by Telemetry Data' },
    upload: { title: 'Dataset Management', subtitle: 'Ingestion, Cleaning Pipeline & Historical Provenance' },
  }

  const currentInfo = pageTitles[page] || { title: 'Overview', subtitle: 'Management Dashboard' }

  return (
    <>
      {/* Left Sleek Icon Rail Sidebar (Reference Layout) */}
      <aside className="sidebar-rail">
        {/* Geometric Diamond Star Logo */}
        <div className="brand-icon-logo" onClick={() => setPage('overview')} title="EVision / POLAR-EMS">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="#ffffff" />
          </svg>
        </div>

        {/* Main Rail Navigation Icons */}
        <nav className="rail-nav">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              className={`rail-item ${page === item.id ? 'active' : ''}`}
              onClick={() => setPage(item.id)}
            >
              <span style={{ fontSize: item.id === 'overview' ? 20 : 16 }}>{item.icon}</span>
              <span className="tooltip">{item.label}</span>
            </a>
          ))}
        </nav>

        {/* Bottom System & Logout Controls */}
        <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
          <div
            className="rail-item"
            style={{ width: 38, height: 38 }}
            onClick={() => setPage('upload')}
            title="System Settings & Database"
          >
            <span style={{ fontSize: 15 }}>⚙</span>
            <span className="tooltip">Settings &amp; Data</span>
          </div>
          <div
            className="rail-item"
            style={{ width: 38, height: 38 }}
            onClick={refreshStatus}
            title="Refresh System Telemetry"
          >
            <span style={{ fontSize: 15 }}>↻</span>
            <span className="tooltip">Refresh Engine</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-container">
        {/* Top App Header (Reference Screenshot Style) */}
        <header className="app-header">
          <div className="header-title-section">
            <h1>{currentInfo.title}</h1>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
            {/* Search Pill */}
            <div className="header-search">
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>🔍</span>
              <input
                type="text"
                placeholder="Search metrics, telemetry..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Connection Status Pill */}
            <div
              className={`badge ${mdmStatus?.has_data ? 'safe' : 'caution'}`}
              style={{ padding: '6px 12px', fontSize: 11, borderRadius: 20 }}
            >
              <span className={`dot ${mdmStatus?.has_data ? 'green' : 'amber'}`} />
              {mdmStatus?.has_data ? `${mdmStatus.records_count.toLocaleString()} Records Active` : 'No Dataset Connected'}
            </div>

            {/* User Profile Badge (Reference Style) */}
            <div className="header-user-badge">
              <div className="user-avatar">
                <span>EP</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#ffffff' }}>Emma Parson</span>
                <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>emma.pars@polar.gov</span>
              </div>
              <span style={{ fontSize: 9, color: 'var(--text-dim)', marginLeft: 2 }}>▼</span>
            </div>

            {/* Notification Bell */}
            <div className="header-icon-btn" title="Operational Alerts" onClick={() => setPage('overview')}>
              <span style={{ fontSize: 14 }}>🔔</span>
            </div>
          </div>
        </header>

        {/* Render Active Analytics Page */}
        <ErrorBoundary key={page}>
          {pages[page] ?? <MdmOverviewPage onNavigate={setPage} />}
        </ErrorBoundary>
      </main>
    </>
  )
}
