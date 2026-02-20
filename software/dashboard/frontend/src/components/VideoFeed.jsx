import React, { useState } from 'react'

export default function VideoFeed() {
  const [showFeed, setShowFeed] = useState(true)
  const src = '/stream/color'

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 12px', borderBottom: '1px solid #334155',
      }}>
        <span className="card-title" style={{ marginBottom: 0 }}>Camera</span>
        <button
          className="btn btn-gray btn-sm"
          onClick={() => setShowFeed(v => !v)}
        >
          {showFeed ? '⏸ Verbergen' : '▶ Tonen'}
        </button>
      </div>

      {showFeed ? (
        <div style={{ position: 'relative', background: '#000', minHeight: 180 }}>
          <img
            src={src}
            alt="Live camera"
            style={{ width: '100%', display: 'block', maxHeight: 300, objectFit: 'contain' }}
            onError={(e) => { e.target.style.display = 'none' }}
          />
          {/* Overlay label */}
          <div style={{
            position: 'absolute', top: 8, left: 8,
            background: 'rgba(0,0,0,0.6)', color: '#fff',
            padding: '2px 8px', borderRadius: 4, fontSize: 11,
          }}>
            LIVE • OAK-D Lite
          </div>
        </div>
      ) : (
        <div style={{
          height: 60, display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#475569', fontSize: 12,
        }}>
          Camera verborgen
        </div>
      )}
    </div>
  )
}
