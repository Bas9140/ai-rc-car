import React, { useState } from 'react'
import { apiPost, apiDelete } from '../hooks/useApi'

export default function WaypointList({ waypoints = [], onRefresh }) {
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  async function handleClear() {
    if (!confirm('Alle waypoints wissen?')) return
    setLoading(true)
    try {
      await apiDelete('/api/waypoints')
      onRefresh?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleStart() {
    setLoading(true)
    try {
      await apiPost('/api/navigation/start')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handlePause() {
    await apiPost('/api/navigation/pause').catch(() => {})
  }

  async function handleResume() {
    await apiPost('/api/navigation/resume').catch(() => {})
  }

  const statusIcon = (s) => {
    if (s === 'done')   return '✅'
    if (s === 'active') return '➤'
    return '○'
  }

  const statusColor = (s) => {
    if (s === 'done')   return '#4ade80'
    if (s === 'active') return '#fbbf24'
    return '#64748b'
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span className="card-title" style={{ marginBottom: 0 }}>
          Waypoints ({waypoints.length})
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-green btn-sm" onClick={handleStart}
            disabled={loading || waypoints.length === 0}>▶ Start</button>
          <button className="btn btn-yellow btn-sm" onClick={handlePause}
            disabled={loading}>⏸</button>
          <button className="btn btn-blue btn-sm" onClick={handleResume}
            disabled={loading}>▶▶</button>
          <button className="btn btn-gray btn-sm" onClick={handleClear}
            disabled={loading}>🗑</button>
        </div>
      </div>

      {error && (
        <div style={{ color: '#f87171', fontSize: 11, marginBottom: 6 }}>{error}</div>
      )}

      {waypoints.length === 0 ? (
        <div style={{ color: '#64748b', fontSize: 12, padding: '4px 0' }}>
          Klik op de kaart om waypoints toe te voegen
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
          {waypoints.map((wp, i) => (
            <div key={wp.wp_id ?? i} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 8px', background: '#0f172a', borderRadius: 6,
            }}>
              <span style={{ color: statusColor(wp.status), fontSize: 14, minWidth: 18 }}>
                {statusIcon(wp.status)}
              </span>
              <span style={{ flex: 1, fontSize: 12 }}>{wp.label}</span>
              <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                {wp.latitude?.toFixed(5)}, {wp.longitude?.toFixed(5)}
              </span>
              <span style={{ fontSize: 11, color: '#475569' }}>r={wp.radius_m}m</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
