import React, { useEffect, useRef, useState } from 'react'
import { MdmStatus } from '../api'

interface MdmFilterBarProps {
  status: MdmStatus | null
  selectedStation: string
  onStationChange: (station: string) => void
  startDate: string
  onStartDateChange: (date: string) => void
  endDate: string
  onEndDateChange: (date: string) => void
  onRefresh?: () => void
}

export const MdmFilterBar: React.FC<MdmFilterBarProps> = ({
  status,
  selectedStation,
  onStationChange,
  startDate,
  onStartDateChange,
  endDate,
  onEndDateChange,
  onRefresh,
}) => {
  const [stationOpen, setStationOpen] = useState(false)
  const [periodOpen, setPeriodOpen] = useState(false)
  const [customRangeActive, setCustomRangeActive] = useState(false)

  const stationRef = useRef<HTMLDivElement>(null)
  const periodRef = useRef<HTMLDivElement>(null)

  // Close popovers on click outside or escape key
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (stationRef.current && !stationRef.current.contains(e.target as Node)) {
        setStationOpen(false)
      }
      if (periodRef.current && !periodRef.current.contains(e.target as Node)) {
        setPeriodOpen(false)
      }
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setStationOpen(false)
        setPeriodOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  if (!status || !status.has_data) {
    return null
  }

  const stations = ['All Stations', ...(status.stations || [])]

  // Calculate quick preset date helper
  const handlePresetSelect = (preset: 'all' | '7d' | '30d' | '90d' | 'custom') => {
    if (preset === 'all') {
      onStartDateChange('')
      onEndDateChange('')
      setCustomRangeActive(false)
      setPeriodOpen(false)
      return
    }

    if (preset === 'custom') {
      setCustomRangeActive(true)
      return
    }

    // If we have an end date in dataset, compute backwards from that, otherwise from today
    const baseDate = status.date_range_end ? new Date(status.date_range_end) : new Date()
    const days = preset === '7d' ? 7 : preset === '30d' ? 30 : 90
    const start = new Date(baseDate)
    start.setDate(start.getDate() - days)

    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    onStartDateChange(fmt(start))
    onEndDateChange(status.date_range_end ? status.date_range_end.slice(0, 10) : fmt(baseDate))
    setCustomRangeActive(false)
    setPeriodOpen(false)
  }

  // Active period label calculation
  let periodLabel = 'All Time'
  if (startDate || endDate) {
    if (startDate && endDate) {
      periodLabel = `${startDate.slice(5)} → ${endDate.slice(5)}`
    } else if (startDate) {
      periodLabel = `From ${startDate.slice(5)}`
    } else {
      periodLabel = `Until ${endDate.slice(5)}`
    }
  }

  const activeStationLabel = selectedStation === 'All' || !selectedStation ? 'All Stations' : selectedStation

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: '10px 16px',
        marginBottom: 20,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 14,
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
        {/* Compact Station Dropdown */}
        <div className="filter-dropdown" ref={stationRef}>
          <button
            type="button"
            className={`filter-btn ${stationOpen ? 'open' : ''} ${selectedStation !== 'All' ? 'active-filter' : ''}`}
            onClick={() => {
              setStationOpen(!stationOpen)
              setPeriodOpen(false)
            }}
          >
            <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Station:
            </span>
            <span style={{ fontWeight: 600 }}>{activeStationLabel}</span>
            <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>▼</span>
          </button>

          {stationOpen && (
            <div className="popover-menu" style={{ width: 220 }}>
              <div style={{ padding: '6px 10px 4px', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
                Select Station Context
              </div>
              {stations.map((st) => {
                const val = st === 'All Stations' ? 'All' : st
                const isSelected = selectedStation === val || (val === 'All' && selectedStation === '')
                return (
                  <button
                    key={st}
                    type="button"
                    className={`popover-item ${isSelected ? 'active' : ''}`}
                    onClick={() => {
                      onStationChange(val)
                      setStationOpen(false)
                    }}
                  >
                    <span>{st}</span>
                    {isSelected && <span style={{ color: 'var(--accent)', fontSize: 12 }}>✓</span>}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Compact Period / Date Range Popover */}
        <div className="filter-dropdown" ref={periodRef}>
          <button
            type="button"
            className={`filter-btn ${periodOpen ? 'open' : ''} ${startDate || endDate ? 'active-filter' : ''}`}
            onClick={() => {
              setPeriodOpen(!periodOpen)
              setStationOpen(false)
            }}
          >
            <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Period:
            </span>
            <span style={{ fontWeight: 600 }}>{periodLabel}</span>
            <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>▼</span>
          </button>

          {periodOpen && (
            <div className="popover-menu" style={{ width: 250 }}>
              <div style={{ padding: '6px 10px 4px', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
                Filter Period
              </div>

              <button
                type="button"
                className={`popover-item ${!startDate && !endDate ? 'active' : ''}`}
                onClick={() => handlePresetSelect('all')}
              >
                <span>All Available Data</span>
                {!startDate && !endDate && <span style={{ color: 'var(--accent)', fontSize: 12 }}>✓</span>}
              </button>

              <button
                type="button"
                className="popover-item"
                onClick={() => handlePresetSelect('7d')}
              >
                <span>Last 7 Days</span>
              </button>

              <button
                type="button"
                className="popover-item"
                onClick={() => handlePresetSelect('30d')}
              >
                <span>Last 30 Days</span>
              </button>

              <button
                type="button"
                className="popover-item"
                onClick={() => handlePresetSelect('90d')}
              >
                <span>Last 90 Days</span>
              </button>

              <button
                type="button"
                className={`popover-item ${customRangeActive ? 'active' : ''}`}
                onClick={() => handlePresetSelect('custom')}
              >
                <span>Custom Date Range...</span>
                {customRangeActive && <span style={{ color: 'var(--accent)', fontSize: 12 }}>▼</span>}
              </button>

              {customRangeActive && (
                <div style={{ padding: '10px 8px 6px', borderTop: '1px solid var(--border)', marginTop: 6, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>From:</span>
                    <input
                      type="text"
                      placeholder={status.date_range_start?.slice(0, 10) || 'YYYY-MM-DD'}
                      value={startDate}
                      onChange={(e) => onStartDateChange(e.target.value)}
                      style={{
                        background: 'var(--bg)',
                        color: 'var(--text-main)',
                        border: '1px solid var(--border)',
                        borderRadius: 4,
                        padding: '6px 8px',
                        fontSize: 12,
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>To:</span>
                    <input
                      type="text"
                      placeholder={status.date_range_end?.slice(0, 10) || 'YYYY-MM-DD'}
                      value={endDate}
                      onChange={(e) => onEndDateChange(e.target.value)}
                      style={{
                        background: 'var(--bg)',
                        color: 'var(--text-main)',
                        border: '1px solid var(--border)',
                        borderRadius: 4,
                        padding: '6px 8px',
                        fontSize: 12,
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, marginTop: 4 }}>
                    <button
                      type="button"
                      onClick={() => {
                        onStartDateChange('')
                        onEndDateChange('')
                        setCustomRangeActive(false)
                        setPeriodOpen(false)
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        fontSize: 11,
                        cursor: 'pointer',
                        padding: '4px 8px',
                      }}
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      onClick={() => setPeriodOpen(false)}
                      style={{
                        background: 'var(--accent)',
                        color: '#000',
                        fontWeight: 700,
                        border: 'none',
                        borderRadius: 4,
                        fontSize: 11,
                        cursor: 'pointer',
                        padding: '4px 10px',
                      }}
                    >
                      Apply
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Reset Filter Button if any active filter */}
        {(selectedStation !== 'All' || startDate || endDate) && (
          <button
            type="button"
            onClick={() => {
              onStationChange('All')
              onStartDateChange('')
              onEndDateChange('')
              setCustomRangeActive(false)
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--accent)',
              fontSize: 12,
              cursor: 'pointer',
              padding: '6px 8px',
              textDecoration: 'underline',
            }}
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Dataset Summary Pill & Refresh */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            background: 'var(--bg)',
            padding: '5px 12px',
            borderRadius: 6,
            border: '1px solid var(--border)',
          }}
        >
          <strong style={{ color: 'var(--accent)' }}>{status.records_count.toLocaleString()}</strong> records ·{' '}
          <strong style={{ color: 'var(--text-main)' }}>{status.stations_count}</strong> station{status.stations_count === 1 ? '' : 's'}
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="btn"
            style={{ padding: '5px 10px', fontSize: 12 }}
            title="Refresh Data"
          >
            ↻ Refresh
          </button>
        )}
      </div>
    </div>
  )
}
