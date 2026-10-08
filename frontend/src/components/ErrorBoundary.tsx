import React, { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallbackTitle?: string
  onReset?: () => void
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo)
    this.setState({ error, errorInfo })
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    if (this.props.onReset) {
      this.props.onReset()
    }
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, maxWidth: 800, margin: '40px auto' }}>
          <div
            className="card"
            style={{
              padding: '32px 28px',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              background: 'rgba(239, 68, 68, 0.05)',
              borderRadius: 12,
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
            <h3 style={{ fontSize: 18, color: 'var(--text-main)', marginBottom: 8, fontWeight: 700 }}>
              {this.props.fallbackTitle || 'A rendering error occurred'}
            </h3>
            <p style={{ color: 'var(--text-dim)', fontSize: 13.5, marginBottom: 20, lineHeight: 1.5 }}>
              {this.state.error?.message || 'An unexpected error occurred while rendering this page.'}
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                className="btn btn-primary"
                onClick={this.handleRetry}
                style={{ padding: '8px 20px', fontSize: 13 }}
              >
                ↻ Retry Page
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  this.setState({ hasError: false, error: null, errorInfo: null })
                  window.location.reload()
                }}
                style={{ padding: '8px 20px', fontSize: 13 }}
              >
                Reload Application
              </button>
            </div>
            {this.state.error?.stack && (
              <details style={{ marginTop: 20, textAlign: 'left', fontSize: 11, color: 'var(--text-muted)' }}>
                <summary style={{ cursor: 'pointer', marginBottom: 8 }}>View diagnostic details</summary>
                <pre
                  style={{
                    background: 'var(--bg-main)',
                    padding: 12,
                    borderRadius: 6,
                    overflowX: 'auto',
                    maxHeight: 180,
                  }}
                >
                  {this.state.error.stack}
                </pre>
              </details>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
