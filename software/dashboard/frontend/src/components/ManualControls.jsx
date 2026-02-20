import React, { useEffect, useRef, useCallback, useState } from 'react'

const THROTTLE_STEP = 0.3   // Per knop-druk
const STEER_STEP    = 0.4

/**
 * ManualControls – D-pad + toetsenbord + touchscreen rijden.
 *
 * Stuurt elke 100ms een manual_cmd via WebSocket als een toets ingedrukt is.
 * Bij loslaten: nul-commando sturen.
 */
export default function ManualControls({ send, mode }) {
  const keysRef   = useRef(new Set())
  const cmdRef    = useRef({ linear_x: 0, angular_z: 0 })
  const timerRef  = useRef(null)
  const [display, setDisplay] = useState({ linear_x: 0, angular_z: 0 })

  const active = mode === 'manual'

  const publishCmd = useCallback(() => {
    const keys = keysRef.current
    let linear_x  = 0
    let angular_z = 0

    if (keys.has('ArrowUp')    || keys.has('w') || keys.has('W')) linear_x  =  THROTTLE_STEP
    if (keys.has('ArrowDown')  || keys.has('s') || keys.has('S')) linear_x  = -THROTTLE_STEP
    if (keys.has('ArrowLeft')  || keys.has('a') || keys.has('A')) angular_z =  STEER_STEP
    if (keys.has('ArrowRight') || keys.has('d') || keys.has('D')) angular_z = -STEER_STEP

    cmdRef.current = { linear_x, angular_z }
    setDisplay({ linear_x, angular_z })

    if (active) {
      send({ type: 'manual_cmd', data: { linear_x, angular_z } })
    }
  }, [send, active])

  // Toetsenbord
  useEffect(() => {
    const down = (e) => { keysRef.current.add(e.key) }
    const up   = (e) => { keysRef.current.delete(e.key) }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup',   up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup',   up)
    }
  }, [])

  // 10 Hz publish loop
  useEffect(() => {
    timerRef.current = setInterval(publishCmd, 100)
    return () => clearInterval(timerRef.current)
  }, [publishCmd])

  // D-pad knop helpers
  function press(key)   { keysRef.current.add(key) }
  function release(key) { keysRef.current.delete(key) }

  const btnProps = (key) => ({
    onPointerDown:   () => press(key),
    onPointerUp:     () => release(key),
    onPointerLeave:  () => release(key),
  })

  const DpadBtn = ({ k, children, style }) => (
    <button
      className="btn btn-gray"
      {...btnProps(k)}
      style={{
        width: 52, height: 52, fontSize: 20,
        userSelect: 'none', touchAction: 'none',
        opacity: active ? 1 : 0.4, cursor: active ? 'pointer' : 'not-allowed',
        ...style,
      }}
      disabled={!active}
    >
      {children}
    </button>
  )

  const barW = Math.abs(display.angular_z / STEER_STEP) * 50   // %
  const barDir = display.angular_z > 0 ? 'left' : 'right'

  return (
    <div className="card">
      <div className="card-title">
        Handmatig rijden
        {!active && <span style={{ color: '#f87171', marginLeft: 8, textTransform: 'none', fontWeight: 400 }}>
          (schakel naar 'Handmatig' modus)
        </span>}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
        {/* D-pad */}
        <div style={{ display: 'grid', gridTemplateColumns: '52px 52px 52px', gap: 4 }}>
          <div />
          <DpadBtn k="ArrowUp">▲</DpadBtn>
          <div />
          <DpadBtn k="ArrowLeft">◄</DpadBtn>
          <div style={{
            width: 52, height: 52, background: '#0f172a',
            borderRadius: 7, display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: 18,
          }}>🚗</div>
          <DpadBtn k="ArrowRight">►</DpadBtn>
          <div />
          <DpadBtn k="ArrowDown">▼</DpadBtn>
          <div />
        </div>

        {/* Status + stuurmeter */}
        <div style={{ flex: 1, minWidth: 150 }}>
          <div className="stat-row">
            <span className="stat-label">Vooruit</span>
            <span className="stat-value">{display.linear_x > 0 ? '▲' : display.linear_x < 0 ? '▼' : '–'}</span>
          </div>
          <div style={{ marginTop: 8 }}>
            <div className="stat-label" style={{ marginBottom: 4 }}>Stuur</div>
            <div style={{ background: '#0f172a', borderRadius: 4, height: 8, position: 'relative' }}>
              <div style={{
                position: 'absolute',
                top: 0, bottom: 0,
                width: `${barW}%`,
                [barDir]: '50%',
                background: '#3b82f6',
                borderRadius: 4,
                transition: 'width 0.1s',
              }} />
              {/* Center line */}
              <div style={{
                position: 'absolute', left: '50%', top: 0, bottom: 0,
                width: 2, background: '#475569', transform: 'translateX(-50%)',
              }} />
            </div>
          </div>
          <div style={{ color: '#64748b', fontSize: 11, marginTop: 8 }}>
            Toetsenbord: WASD of pijltoetsen
          </div>
        </div>
      </div>
    </div>
  )
}
