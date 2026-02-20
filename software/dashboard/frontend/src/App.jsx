import React, { useState, useEffect, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { apiPost } from './hooks/useApi'
import TopBar         from './components/TopBar'
import StatusPanel    from './components/StatusPanel'
import VideoFeed      from './components/VideoFeed'
import MapView        from './components/MapView'
import ManualControls from './components/ManualControls'
import WaypointList   from './components/WaypointList'
import DetectionList  from './components/DetectionList'

export default function App() {
  const [telemetry,   setTelemetry]   = useState({})
  const [detections,  setDetections]  = useState([])
  const [waypoints,   setWaypoints]   = useState([])
  const [mode,        setMode]        = useState('idle')

  // ── WebSocket ────────────────────────────────────────────────────────────
  const { send, connected } = useWebSocket({
    onMessage: useCallback((msg) => {
      if (msg.type === 'status') {
        setTelemetry(msg.data ?? {})
        if (msg.data?.mode) setMode(msg.data.mode)
      } else if (msg.type === 'detections') {
        setDetections(msg.data ?? [])
      } else if (msg.type === 'waypoints') {
        setWaypoints(msg.data ?? [])
      }
    }, []),
  })

  // ── Waypoints ophalen ────────────────────────────────────────────────────
  async function fetchWaypoints() {
    try {
      const res = await fetch('/api/waypoints')
      if (res.ok) setWaypoints(await res.json())
    } catch { /* stil falen */ }
  }

  useEffect(() => { fetchWaypoints() }, [])

  // ── Waypoint toevoegen via kaart klik ────────────────────────────────────
  async function handleAddWaypoint(lat, lon) {
    try {
      await apiPost('/api/waypoints', { latitude: lat, longitude: lon, radius_m: 1.5 })
      await fetchWaypoints()
    } catch (err) {
      console.error('Waypoint toevoegen mislukt:', err)
    }
  }

  // ── Manual cmd via WebSocket sturen ─────────────────────────────────────
  function sendCmd(msg) {
    send(msg)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#020617', display: 'flex', flexDirection: 'column' }}>
      <TopBar
        mode={mode}
        connected={connected}
        onModeChange={setMode}
      />

      <div style={{
        flex: 1,
        padding: '16px',
        display: 'grid',
        gap: 16,
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gridTemplateRows: 'auto',
        alignItems: 'start',
      }}>

        {/* Linkerkolom: video + detecties */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <VideoFeed />
          <DetectionList detections={detections} />
        </div>

        {/* Middelste kolom: kaart + waypoints */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <MapView
            telemetry={telemetry}
            waypoints={waypoints}
            onAddWaypoint={handleAddWaypoint}
          />
          <WaypointList
            waypoints={waypoints}
            onRefresh={fetchWaypoints}
          />
        </div>

        {/* Rechterkolom: status + handmatig rijden */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <StatusPanel telemetry={telemetry} wsStatus={connected ? 'connected' : 'disconnected'} />
          <ManualControls send={sendCmd} mode={mode} />
        </div>

      </div>
    </div>
  )
}
