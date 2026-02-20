import React from 'react'

const CLASS_COLORS = {
  person:     '#4ade80',
  car:        '#f87171',
  truck:      '#f87171',
  motorcycle: '#f87171',
  bus:        '#f87171',
  cat:        '#fbbf24',
  dog:        '#fbbf24',
}

function classColor(name) {
  return CLASS_COLORS[name?.toLowerCase()] ?? '#94a3b8'
}

export default function DetectionList({ detections = [] }) {
  return (
    <div className="card">
      <div className="card-title">Detecties ({detections.length})</div>

      {detections.length === 0 ? (
        <div style={{ color: '#64748b', fontSize: 12, padding: '4px 0' }}>
          Geen objecten gedetecteerd
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {detections.map((d, i) => (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '5px 8px',
              background: '#0f172a',
              borderRadius: 6,
              borderLeft: `3px solid ${classColor(d.class_name)}`,
            }}>
              <span style={{
                color: classColor(d.class_name),
                fontWeight: 700,
                fontSize: 12,
                minWidth: 70,
              }}>
                {d.class_name}
              </span>

              {/* Confidence bar */}
              <div style={{ flex: 1, height: 4, background: '#334155', borderRadius: 2 }}>
                <div style={{
                  width: `${Math.round(d.confidence * 100)}%`,
                  height: '100%',
                  background: classColor(d.class_name),
                  borderRadius: 2,
                  transition: 'width 0.3s',
                }} />
              </div>

              <span style={{ fontSize: 11, color: '#94a3b8', minWidth: 36, textAlign: 'right' }}>
                {Math.round(d.confidence * 100)}%
              </span>

              {d.distance_m != null && (
                <span style={{ fontSize: 11, color: '#e2e8f0', minWidth: 40, textAlign: 'right' }}>
                  {d.distance_m}m
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
