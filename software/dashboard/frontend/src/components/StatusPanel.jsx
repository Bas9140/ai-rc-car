import React from 'react'

function avoidanceBadge(status) {
  const map = {
    clear:   ['badge badge-green',  'Vrij'],
    warning: ['badge badge-yellow', 'Waarschuwing'],
    danger:  ['badge badge-red',    'Gevaar'],
    stop:    ['badge badge-red',    'Stop'],
  }
  const [cls, label] = map[status] ?? ['badge badge-gray', status ?? '–']
  return <span className={cls}>{label}</span>
}

function modeBadge(mode) {
  const map = {
    idle:       ['badge badge-gray',   'Inactief'],
    manual:     ['badge badge-blue',   'Handmatig'],
    autonomous: ['badge badge-green',  'Autonoom'],
    follow_me:  ['badge badge-yellow', 'Volgen'],
    emergency_stop: ['badge badge-red','NOODSTOP'],
  }
  const [cls, label] = map[mode] ?? ['badge badge-gray', mode ?? '–']
  return <span className={cls}>{label}</span>
}

function gpsIcon(quality) {
  if (quality <= 0) return '❌ Geen fix'
  if (quality === 1) return '✅ GPS'
  if (quality === 2) return '✅ DGPS'
  return '✅ RTK'
}

export default function StatusPanel({ telemetry, wsStatus }) {
  const t = telemetry ?? {}

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="card-title">Status</div>

      {wsStatus !== 'connected' && (
        <div style={{
          background: '#7f1d1d', color: '#fca5a5',
          borderRadius: 6, padding: '6px 10px', fontSize: 12, fontWeight: 600,
        }}>
          ⚠ WebSocket: {wsStatus === 'connecting' ? 'Verbinden…' : 'Verbroken – herverbinden…'}
        </div>
      )}

      {!t.ros_connected && wsStatus === 'connected' && (
        <div style={{
          background: '#713f12', color: '#fbbf24',
          borderRadius: 6, padding: '6px 10px', fontSize: 12, fontWeight: 600,
        }}>
          ⚠ ROS2 niet verbonden (mock mode)
        </div>
      )}

      <div className="stat-row">
        <span className="stat-label">Modus</span>
        {modeBadge(t.emergency_stop ? 'emergency_stop' : t.mode)}
      </div>

      <div className="stat-row">
        <span className="stat-label">GPS</span>
        <span className="stat-value" style={{ fontSize: 12 }}>
          {gpsIcon(t.gps_quality)}
        </span>
      </div>

      {t.latitude != null && (
        <div className="stat-row">
          <span className="stat-label">Positie</span>
          <span className="stat-value" style={{ fontSize: 11, fontFamily: 'monospace' }}>
            {t.latitude?.toFixed(5)}° N<br />
            {t.longitude?.toFixed(5)}° E
          </span>
        </div>
      )}

      {t.heading_deg != null && (
        <div className="stat-row">
          <span className="stat-label">Koers</span>
          <span className="stat-value">{t.heading_deg?.toFixed(1)}°</span>
        </div>
      )}

      <div className="stat-row">
        <span className="stat-label">Obstakels</span>
        {avoidanceBadge(t.avoidance_status)}
      </div>

      <div className="stat-row">
        <span className="stat-label">Navigatie</span>
        <span className="stat-value" style={{ textTransform: 'capitalize' }}>
          {t.nav_status ?? '–'}
          {t.nav_distance_m != null && ` (${t.nav_distance_m}m)`}
        </span>
      </div>

      {t.tracking?.tracking && (
        <div className="stat-row">
          <span className="stat-label">Volgt</span>
          <span className="stat-value">
            {t.tracking.class_name} @ {t.tracking.distance_m}m
          </span>
        </div>
      )}
    </div>
  )
}
