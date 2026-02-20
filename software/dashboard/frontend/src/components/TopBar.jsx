import React, { useState } from 'react'
import { apiPost } from '../hooks/useApi'

const MODES = [
  { value: 'manual',     label: 'Handmatig' },
  { value: 'follow',     label: 'Volgen' },
  { value: 'autonomous', label: 'Autonoom' },
  { value: 'idle',       label: 'Wacht' },
]

export default function TopBar({ mode, connected, onModeChange }) {
  const [switching, setSwitching] = useState(false)
  const [stopping,  setStopping]  = useState(false)

  async function handleModeChange(e) {
    const newMode = e.target.value
    setSwitching(true)
    try {
      await apiPost('/api/mission/mode', { mode: newMode })
      onModeChange?.(newMode)
    } catch (err) {
      console.error('Mode switch failed:', err)
    } finally {
      setSwitching(false)
    }
  }

  async function handleEmergencyStop() {
    setStopping(true)
    try {
      await apiPost('/api/mission/stop')
    } catch (err) {
      console.error('E-stop failed:', err)
    } finally {
      // Keep red state for 1.5s so user sees it activated
      setTimeout(() => setStopping(false), 1500)
    }
  }

  const connColor = connected ? '#4ade80' : '#f87171'
  const connLabel = connected ? 'Verbonden' : 'Verbroken'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '10px 20px',
      background: '#0f172a',
      borderBottom: '1px solid #1e293b',
      gap: 16,
      flexWrap: 'wrap',
    }}>
      {/* Logo / titel */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 20 }}>🚗</span>
        <span style={{ fontWeight: 700, fontSize: 15, color: '#e2e8f0', letterSpacing: 0.5 }}>
          AI RC Car
        </span>
        <span style={{
          fontSize: 10, fontWeight: 600, color: connColor,
          background: `${connColor}22`, borderRadius: 12,
          padding: '2px 8px', letterSpacing: 0.5,
        }}>
          ⬤ {connLabel}
        </span>
      </div>

      {/* Modus selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>Modus</span>
        <select
          value={mode ?? 'idle'}
          onChange={handleModeChange}
          disabled={switching}
          style={{
            background: '#1e293b', color: '#e2e8f0',
            border: '1px solid #334155', borderRadius: 6,
            padding: '5px 10px', fontSize: 13, cursor: 'pointer',
          }}
        >
          {MODES.map(m => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>

        {/* Emergency stop */}
        <button
          onClick={handleEmergencyStop}
          disabled={stopping}
          style={{
            background: stopping ? '#7f1d1d' : '#dc2626',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            padding: '6px 16px',
            fontWeight: 700,
            fontSize: 13,
            cursor: stopping ? 'default' : 'pointer',
            letterSpacing: 0.5,
            transition: 'background 0.2s',
          }}
        >
          {stopping ? '⛔ GESTOPT' : '⛔ NOODSTOP'}
        </button>
      </div>
    </div>
  )
}
