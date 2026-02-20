import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import 'leaflet/dist/leaflet.css'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(e) { return { error: e } }
  render() {
    if (this.state.error) return (
      <div style={{ padding: 32, color: '#f87171', fontFamily: 'monospace', background: '#0f172a', minHeight: '100vh' }}>
        <h2>Dashboard fout</h2>
        <pre style={{ marginTop: 16, fontSize: 13, whiteSpace: 'pre-wrap' }}>
          {this.state.error?.toString()}{'\n'}{this.state.error?.stack}
        </pre>
      </div>
    )
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
)
