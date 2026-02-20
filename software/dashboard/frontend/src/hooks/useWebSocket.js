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
export function useWebSocket({ onMessage } = {}) {
  const wsRef      = useRef(null)
  const timerRef   = useRef(null)
  const onMsgRef   = useRef(onMessage)

  const [connected, setConnected] = useState(false)

  // Altijd de laatste onMessage callback bijhouden zonder reconnect te triggeren
  useEffect(() => { onMsgRef.current = onMessage }, [onMessage])

  const connect = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url   = `${proto}://${window.location.host}/ws`
    const ws    = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
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
        onMsgRef.current?.(msg)
      } catch (_) {}
    }

    ws.onclose = () => {
      setConnected(false)
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

  return { connected, send }
}
