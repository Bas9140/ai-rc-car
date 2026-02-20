import { useEffect, useRef, useState, useCallback } from 'react'

const RECONNECT_MS = 2000

/**
 * WebSocket verbinding met auto-reconnect.
 *
 * Returns:
 *   status     – 'connecting' | 'connected' | 'disconnected'
 *   telemetry  – laatste status payload van de backend
 *   send(msg)  – stuur JSON object naar backend
 */
export function useWebSocket() {
  const wsRef      = useRef(null)
  const timerRef   = useRef(null)

  const [wsStatus,  setWsStatus]  = useState('connecting')
  const [telemetry, setTelemetry] = useState(null)

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url   = `${proto}://${window.location.host}/ws`
    const ws    = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setWsStatus('connected')
      clearTimeout(timerRef.current)
      // Ping elke 30s om verbinding levend te houden
      timerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30_000)
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'status') {
          setTelemetry(msg.data)
        }
        // detections worden ook in telemetry.detections opgenomen
      } catch (_) {}
    }

    ws.onclose = () => {
      setWsStatus('disconnected')
      clearInterval(timerRef.current)
      timerRef.current = setTimeout(connect, RECONNECT_MS)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(timerRef.current)
      clearInterval(timerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return { wsStatus, telemetry, send }
}
