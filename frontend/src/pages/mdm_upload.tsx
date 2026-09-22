import React, { useEffect, useRef, useState } from 'react'
import { clearMdmData, getMdmStatus, MdmStatus, uploadDatasetCsv, UploadResponse } from '../api'

interface MdmUploadPageProps {
  onNavigate?: (page: string) => void
  onUploadSuccess?: () => void
}

export const MdmUploadPage: React.FC<MdmUploadPageProps> = ({ onNavigate, onUploadSuccess }) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [uploading, setUploading] = useState<boolean>(false)
  const [lastUploadResult, setLastUploadResult] = useState<UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState<boolean>(false)

  const loadStatus = async () => {
    try {
      const st = await getMdmStatus()
      setStatus(st)
    } catch (err: any) {
      console.error('Failed to load status:', err)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const handleFile = async (file: File) => {
    const fn = file.name.toLowerCase()
    if (!fn.endsWith('.csv') && !fn.endsWith('.xlsx') && !fn.endsWith('.xls')) {
      setError('Please select a valid dataset file (.csv, .xlsx, or .xls).')
      return
    }

    try {
      setUploading(true)
      setError(null)
      const res = await uploadDatasetCsv(file)
      setLastUploadResult(res)
      await loadStatus()
      if (onUploadSuccess) onUploadSuccess()
    } catch (err: any) {
      setError(err.message || 'Dataset upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleClear = async () => {
    if (window.confirm('Are you sure you want to clear all uploaded datasets? This will reset the MDM database.')) {
      try {
        await clearMdmData()
        setLastUploadResult(null)
        await loadStatus()
        if (onUploadSuccess) onUploadSuccess()
      } catch (err: any) {
        setError(err.message || 'Failed to clear data')
      }
    }
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
            Dataset Management &amp; Ingestion
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
            Supported formats: <b style={{ color: 'var(--text-main)' }}>CSV</b>, <b style={{ color: 'var(--text-main)' }}>XLSX</b>, <b style={{ color: 'var(--text-main)' }}>XLS</b> · Automatic schema detection &amp; historical dataset merging
          </p>
        </div>
        {status?.has_data && (
          <button
            onClick={handleClear}
            className="btn"
            style={{
              background: 'var(--bad-dim)',
              borderColor: 'var(--bad)',
              color: 'var(--bad)',
              fontSize: 12,
              padding: '6px 14px',
            }}
          >
            Reset / Clear Data
          </button>
        )}
      </div>

      {error && (
        <div style={{ padding: '10px 14px', background: 'var(--bad-dim)', border: '1px solid var(--bad)', borderRadius: 6, marginBottom: 16, color: 'var(--bad)', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Upload Drop Zone */}
      <div
        className="card"
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          padding: '44px 24px',
          textAlign: 'center',
          border: `1.5px dashed ${dragActive ? 'var(--accent)' : 'rgba(255,255,255,0.14)'}`,
          background: dragActive ? 'var(--accent-dim)' : 'var(--bg-secondary)',
          borderRadius: 10,
          cursor: 'pointer',
          marginBottom: 24,
          transition: 'var(--transition)',
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFile(e.target.files[0])
            }
          }}
        />
        <div style={{ fontSize: 36, marginBottom: 10 }}>📁</div>
        <h3 style={{ margin: '0 0 6px 0', fontSize: 16, fontWeight: 700, color: 'var(--text-main)', textTransform: 'none' }}>
          {uploading ? 'Processing & Merging Operational Dataset...' : 'Drag & Drop Station File or Browse'}
        </h3>
        <p style={{ margin: '0 0 16px 0', fontSize: 13, color: 'var(--text-dim)' }}>
          Supports CSV, XLSX, and XLS workbooks with power telemetry, temperature, or battery data.
        </p>
        <button
          type="button"
          disabled={uploading}
          className="btn btn-primary"
          style={{
            padding: '8px 22px',
            fontSize: 13,
            cursor: uploading ? 'wait' : 'pointer',
          }}
        >
          {uploading ? 'Analyzing Telemetry...' : 'Choose File'}
        </button>
      </div>

      {/* Live Processing Summary Result (Strictly Dynamic) */}
      {lastUploadResult && (
        <div className="card" style={{ marginBottom: 24, border: '1px solid rgba(34, 197, 94, 0.4)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="dot green" />
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: 'var(--text-main)', textTransform: 'none' }}>
                Dataset Processing Summary
              </h3>
            </div>
            {onNavigate && (
              <button
                className="btn btn-primary"
                onClick={() => onNavigate('overview')}
                style={{ padding: '5px 14px', fontSize: 12 }}
              >
                View Analytics Dashboard →
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>File Name</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-main)', marginTop: 2 }}>
                {lastUploadResult.filename}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Rows Detected / Integrated</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--good)', marginTop: 2 }}>
                {lastUploadResult.rows_detected.toLocaleString()} detected → {lastUploadResult.rows_accepted.toLocaleString()} added
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Duplicates Handled</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-main)', marginTop: 2 }}>
                {lastUploadResult.duplicates_removed} rows
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Missing Values Cleaned</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-main)', marginTop: 2 }}>
                {lastUploadResult.missing_values_handled} entries
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Detected Period</div>
              <div style={{ fontSize: 13, color: 'var(--text-main)', marginTop: 2, fontFamily: 'var(--mono)' }}>
                {lastUploadResult.start_date || 'N/A'} → {lastUploadResult.end_date || 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Stations Identified</div>
              <div style={{ fontSize: 13, color: 'var(--text-main)', marginTop: 2 }}>
                {lastUploadResult.stations_detected.join(', ') || 'N/A'}
              </div>
            </div>
          </div>

          {/* Mapped vs Ignored Columns */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, background: 'var(--bg-secondary)', padding: 14, borderRadius: 6, fontSize: 12 }}>
            <div>
              <div style={{ fontWeight: 700, color: 'var(--good)', marginBottom: 6 }}>
                ✓ Mapped Analytics Columns ({Object.keys(lastUploadResult.columns_mapped).length}):
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {Object.entries(lastUploadResult.columns_mapped).map(([raw, canonical]) => (
                  <div key={raw} style={{ color: 'var(--text-dim)' }}>
                    <code style={{ color: 'var(--text-main)', fontFamily: 'var(--mono)', fontSize: 11.5 }}>{raw}</code> → <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{canonical}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div style={{ fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6 }}>
                • Safely Isolated Columns ({lastUploadResult.columns_ignored.length}):
              </div>
              {lastUploadResult.columns_ignored.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>None</div>
              ) : (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {lastUploadResult.columns_ignored.map((col) => (
                    <span
                      key={col}
                      style={{
                        background: 'rgba(255, 255, 255, 0.04)',
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontFamily: 'var(--mono)',
                        fontSize: 11,
                        color: 'var(--text-muted)',
                      }}
                    >
                      {col}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--accent)' }}>
            <strong>Historical Integration:</strong> {lastUploadResult.merge_status}
          </div>
        </div>
      )}

      {/* Connected Datasets Provenance Table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.6 }}>
            Connected Dataset History &amp; Provenance
          </h3>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {status?.datasets_count || 0} dataset{status?.datasets_count === 1 ? '' : 's'} registered
          </span>
        </div>

        {!status?.datasets || status.datasets.length === 0 ? (
          <p style={{ color: 'var(--text-dim)', fontSize: 13, margin: '20px 0', textAlign: 'center' }}>
            No operational datasets uploaded yet. Upload a CSV or Excel file above to begin analysis.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Dataset ID</th>
                  <th>Filename</th>
                  <th>Rows Detected</th>
                  <th>Rows Accepted</th>
                  <th>Duplicates</th>
                  <th>Data Period</th>
                  <th>Stations</th>
                  <th>Uploaded At</th>
                </tr>
              </thead>
              <tbody>
                {status.datasets.map((ds) => (
                  <tr key={ds.id}>
                    <td style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                      {ds.id}
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                      {ds.filename}
                    </td>
                    <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
                      {ds.rows_detected.toLocaleString()}
                    </td>
                    <td style={{ color: 'var(--good)', fontWeight: 600, fontFamily: 'var(--mono)' }}>
                      {ds.rows_accepted.toLocaleString()}
                    </td>
                    <td style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
                      {ds.duplicates_removed}
                    </td>
                    <td style={{ color: 'var(--text-main)', fontFamily: 'var(--mono)' }}>
                      {ds.start_date ? `${ds.start_date.slice(0, 10)} → ${ds.end_date?.slice(0, 10)}` : 'N/A'}
                    </td>
                    <td style={{ color: 'var(--text-dim)' }}>
                      {ds.stations.join(', ')}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--mono)' }}>
                      {new Date(ds.upload_timestamp * 1000).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
