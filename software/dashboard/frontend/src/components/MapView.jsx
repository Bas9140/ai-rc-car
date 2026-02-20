import React, { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'

// ── Aangepaste iconen ──────────────────────────────────────────────────────
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

function makeCarIcon(heading) {
  const deg = heading ?? 0
  return L.divIcon({
    className: '',
    html: `<div style="
      width:28px; height:28px; background:#3b82f6; border-radius:50%;
      border:3px solid #fff; display:flex; align-items:center;
      justify-content:center; transform:rotate(${deg}deg);
      box-shadow:0 0 0 2px #1d4ed8;
    ">
      <div style="width:0;height:0;border-left:5px solid transparent;
        border-right:5px solid transparent;border-bottom:10px solid #fff;
        margin-top:-3px;"></div>
    </div>`,
    iconSize:   [28, 28],
    iconAnchor: [14, 14],
  })
}

function makeWaypointIcon(index, status) {
  const colors = { done: '#4ade80', active: '#fbbf24', pending: '#64748b' }
  const color  = colors[status] ?? '#64748b'
  return L.divIcon({
    className: '',
    html: `<div style="
      width:24px;height:24px;background:${color};border-radius:50%;
      border:2px solid #fff;display:flex;align-items:center;
      justify-content:center;color:#000;font-size:11px;font-weight:700;
      box-shadow:0 1px 4px rgba(0,0,0,0.4);
    ">${index + 1}</div>`,
    iconSize:   [24, 24],
    iconAnchor: [12, 12],
  })
}

// ── Klik-handler component ────────────────────────────────────────────────
function ClickHandler({ onMapClick }) {
  useMapEvents({
    click: (e) => onMapClick(e.latlng.lat, e.latlng.lng),
  })
  return null
}

// ── Auto-center als positie verandert ────────────────────────────────────
function AutoCenter({ lat, lon, follow }) {
  const map = useMap()
  const prevRef = useRef(null)

  useEffect(() => {
    if (!follow || lat == null || lon == null) return
    const key = `${lat.toFixed(5)},${lon.toFixed(5)}`
    if (key !== prevRef.current) {
      prevRef.current = key
      map.setView([lat, lon], map.getZoom())
    }
  }, [lat, lon, follow, map])

  return null
}

// ── Hoofd component ───────────────────────────────────────────────────────
export default function MapView({ telemetry, waypoints = [], onAddWaypoint }) {
  const lat = telemetry?.latitude
  const lon = telemetry?.longitude
  const heading = telemetry?.heading_deg

  // Startpositie: Amsterdam als geen GPS beschikbaar
  const center = lat != null ? [lat, lon] : [52.3676, 4.9041]

  const waypointPositions = waypoints
    .filter(wp => wp.latitude != null)
    .map(wp => [wp.latitude, wp.longitude])

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 12px', borderBottom: '1px solid #334155',
      }}>
        <span className="card-title" style={{ marginBottom: 0 }}>Kaart</span>
        <span style={{ fontSize: 11, color: '#64748b' }}>
          Klik om waypoint toe te voegen
        </span>
      </div>

      <MapContainer
        center={center}
        zoom={18}
        style={{ height: 320, width: '100%' }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <ClickHandler onMapClick={onAddWaypoint} />
        {lat != null && <AutoCenter lat={lat} lon={lon} follow={true} />}

        {/* Auto positie */}
        {lat != null && (
          <Marker position={[lat, lon]} icon={makeCarIcon(heading)}>
            <Popup>
              <strong>Auto</strong><br />
              {lat?.toFixed(5)}° N, {lon?.toFixed(5)}° E<br />
              Koers: {heading?.toFixed(1)}°
            </Popup>
          </Marker>
        )}

        {/* Waypoints */}
        {waypoints.filter(wp => wp.latitude != null).map((wp, i) => (
          <Marker
            key={wp.wp_id ?? i}
            position={[wp.latitude, wp.longitude]}
            icon={makeWaypointIcon(i, wp.status)}
          >
            <Popup>
              <strong>{wp.label}</strong><br />
              {wp.latitude?.toFixed(5)}° N<br />
              {wp.longitude?.toFixed(5)}° E<br />
              Radius: {wp.radius_m}m
            </Popup>
          </Marker>
        ))}

        {/* Route lijn */}
        {waypointPositions.length > 1 && (
          <Polyline
            positions={waypointPositions}
            color="#3b82f6"
            weight={2}
            dashArray="6, 4"
            opacity={0.7}
          />
        )}

        {/* Lijn van auto naar huidig waypoint */}
        {lat != null && waypointPositions.length > 0 && (
          <Polyline
            positions={[[lat, lon], waypointPositions[0]]}
            color="#fbbf24"
            weight={2}
            opacity={0.8}
          />
        )}
      </MapContainer>
    </div>
  )
}
