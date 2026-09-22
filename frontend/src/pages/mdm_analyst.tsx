import React, { useEffect, useRef, useState } from 'react'
import { AiAnalystResponse, askAiAnalyst, getMdmStatus, MdmStatus } from '../api'
import { MdmFilterBar } from '../components/MdmFilterBar'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  responseDetails?: AiAnalystResponse
  timestamp: string
}

interface MdmAnalystPageProps {
  onNavigate?: (page: string) => void
}

const SAMPLE_QUESTIONS = [
  'Why did energy consumption increase this week?',
  'Which station has the highest resource risk?',
  'What caused the recent battery decline?',
  'Which equipment shows abnormal behavior?',
  'What are the major energy consumption peaks?',
  'What changed after the last upload?',
  'What data are you using?',
  'What should the operator monitor today?',
]

export const MdmAnalystPage: React.FC<MdmAnalystPageProps> = ({ onNavigate }) => {
  const [status, setStatus] = useState<MdmStatus | null>(null)
  const [selectedStation, setSelectedStation] = useState<string>('All')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  const [inputQuery, setInputQuery] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init',
      role: 'assistant',
      content:
        'Hello! I am your Antarctic Research Station AI Analyst. I have direct real-time access to your uploaded dataset, computed metrics, and current filters. Ask me anything about station energy demand, equipment anomalies, or resource stress.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])

  const chatEndRef = useRef<HTMLDivElement>(null)

  const loadStatus = async () => {
    try {
      const st = await getMdmStatus()
      setStatus(st)
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async (questionText?: string) => {
    const textToSend = (questionText || inputQuery).trim()
    if (!textToSend || loading) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInputQuery('')
    setLoading(true)

    try {
      const dashboardContext = {
        selected_station: selectedStation,
        date_range: { start: startDate, end: endDate },
        active_module: 'ai_analyst',
      }

      const historyForApi = messages
        .filter((m) => m.id !== 'init')
        .slice(-4)
        .map((m) => ({ role: m.role, content: m.content }))

      const resp = await askAiAnalyst(textToSend, dashboardContext, historyForApi)

      const assistantMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: resp.answer,
        responseDetails: resp,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an issue analyzing your request: ${err.message || 'AI Analyst temporarily unavailable'}.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 100px)' }}>
      {/* Header */}
      <div style={{ marginBottom: 14 }}>
        <h2 style={{ margin: '0 0 4px 0', fontSize: 20, fontWeight: 700, color: 'var(--text-main)' }}>
          AI Operational Analyst
        </h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-dim)' }}>
          Direct analytical query interface backed by empirical station telemetry and resource metrics.
        </p>
      </div>

      {/* Dynamic Filter Bar */}
      <MdmFilterBar
        status={status}
        selectedStation={selectedStation}
        onStationChange={setSelectedStation}
        startDate={startDate}
        onStartDateChange={setStartDate}
        endDate={endDate}
        onEndDateChange={setEndDate}
        onRefresh={loadStatus}
      />

      {/* Empty State Warning if No Data */}
      {status && !status.has_data && (
        <div
          className="card"
          style={{
            padding: '12px 16px',
            background: 'var(--warn-dim)',
            border: '1px solid var(--warn)',
            borderRadius: 8,
            marginBottom: 12,
            fontSize: 13,
            color: 'var(--warn)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>
            ⚠️ <strong>No dataset currently connected.</strong> Upload a station CSV or Excel file to enable data-grounded insights.
          </span>
          {onNavigate && (
            <button
              className="btn btn-primary"
              onClick={() => onNavigate('upload')}
              style={{
                padding: '4px 12px',
                fontSize: 11.5,
              }}
            >
              Upload Data →
            </button>
          )}
        </div>
      )}

      {/* Suggested Quick Questions */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 12 }}>
        {SAMPLE_QUESTIONS.map((q, i) => (
          <button
            key={i}
            type="button"
            onClick={() => handleSend(q)}
            disabled={loading}
            className="btn"
            style={{
              borderRadius: 16,
              padding: '4px 12px',
              fontSize: 11.5,
              fontWeight: 500,
              background: 'var(--bg-secondary)',
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Chat Messages Log Area */}
      <div
        className="card"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          marginBottom: 14,
          background: 'var(--bg-card)',
        }}
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '82%',
                background: msg.role === 'user' ? 'rgba(34, 211, 238, 0.12)' : 'var(--bg-secondary)',
                color: 'var(--text-main)',
                border: `1px solid ${msg.role === 'user' ? 'rgba(34, 211, 238, 0.35)' : 'var(--border)'}`,
                borderRadius: 8,
                padding: '12px 16px',
                fontSize: 13,
                lineHeight: 1.55,
              }}
            >
              {/* Header / Role */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 6,
                  fontSize: 10.5,
                  color: msg.role === 'user' ? 'var(--accent)' : 'var(--text-muted)',
                  fontWeight: 700,
                  letterSpacing: 0.5,
                  gap: 12,
                }}
              >
                <span>{msg.role === 'user' ? 'OPERATOR' : '🤖 AI ANALYST'}</span>
                <span style={{ fontFamily: 'var(--mono)', fontWeight: 500, opacity: 0.8 }}>{msg.timestamp}</span>
              </div>

              {/* Main Answer Content */}
              <div style={{ whiteSpace: 'pre-line', marginBottom: msg.responseDetails ? 10 : 0 }}>
                {msg.content}
              </div>

              {/* Structured Response Breakdown if present */}
              {msg.responseDetails && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
                  {/* Key Metrics */}
                  {msg.responseDetails.key_metrics && msg.responseDetails.key_metrics.length > 0 && (
                    <div>
                      <div style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                        Key Telemetry Metrics:
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {msg.responseDetails.key_metrics.map((km, idx) => (
                          <span
                            key={idx}
                            style={{
                              background: 'var(--accent-dim)',
                              border: '1px solid rgba(34, 211, 238, 0.25)',
                              borderRadius: 4,
                              padding: '2px 8px',
                              fontSize: 11,
                              fontFamily: 'var(--mono)',
                              color: 'var(--accent)',
                            }}
                          >
                            {km}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Evidence */}
                  {msg.responseDetails.evidence && msg.responseDetails.evidence.length > 0 && (
                    <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                      <strong style={{ color: 'var(--text-main)' }}>Evidence Grounding:</strong>{' '}
                      {msg.responseDetails.evidence.join(' · ')}
                    </div>
                  )}

                  {/* Recommendations */}
                  {msg.responseDetails.recommendations && msg.responseDetails.recommendations.length > 0 && (
                    <div style={{ fontSize: 12, color: 'var(--good)', background: 'var(--good-dim)', border: '1px solid rgba(34, 197, 94, 0.25)', padding: '6px 10px', borderRadius: 6 }}>
                      <strong>Operational Action:</strong> {msg.responseDetails.recommendations.join(' ')}
                    </div>
                  )}

                  {/* Data Limitations if any */}
                  {msg.responseDetails.data_limitations && msg.responseDetails.data_limitations.length > 0 && (
                    <div style={{ fontSize: 11, color: 'var(--warn)', fontStyle: 'italic' }}>
                      <strong>Boundary / Limitation:</strong> {msg.responseDetails.data_limitations.join(' ')}
                    </div>
                  )}

                  {/* Source Stamp */}
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'right', marginTop: 2, fontFamily: 'var(--mono)' }}>
                    {msg.responseDetails.source || 'AI Analytics Engine'}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent)', fontSize: 12.5, padding: '8px 12px' }}>
            <span className="dot cyan" />
            <span>AI Analyst is computing answers from current telemetry...</span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Message Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        style={{ display: 'flex', gap: 10 }}
      >
        <input
          type="text"
          placeholder="Ask a question about current station energy, anomalies, or resources..."
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          disabled={loading}
          style={{
            flex: 1,
            background: 'var(--bg-card)',
            color: 'var(--text-main)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '10px 14px',
            fontSize: 13,
            outline: 'none',
          }}
        />
        <button
          type="submit"
          disabled={loading || !inputQuery.trim()}
          className="btn btn-primary"
          style={{
            padding: '0 20px',
            fontSize: 13,
            cursor: loading || !inputQuery.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !inputQuery.trim() ? 0.6 : 1,
          }}
        >
          Ask AI →
        </button>
      </form>
    </div>
  )
}
