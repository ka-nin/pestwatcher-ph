import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { ReportRecord } from '../../lib/api'
import './ProvinceMap.css'

interface ProvinceMapProps {
  latitude: number
  longitude: number
  label: string
  reports?: ReportRecord[]
}

type MapMode = 'satellite' | 'wind'

// Same palette as the risk-zone legend dots (Dashboard.css) so a report pin
// and a risk-level badge always mean the same color across the dashboard.
const SEVERITY_COLOR: Record<string, string> = {
  low: '#4b9e5f',
  medium: '#e0b23b',
  high: '#d3564f',
}

const REPORT_ZOOM = 16

// How far apart (in degrees of lat/lon) to nudge pins that would otherwise
// sit exactly on top of each other — e.g. several reports from the same
// municipality, which all carry that municipality's fixed coordinates
// rather than a real per-sighting GPS pin (see user-mobile's Welcome.jsx).
// ~0.0009 deg is roughly 100m at this latitude, enough to visually separate
// pins without drifting them into a neighboring municipality.
const CLUSTER_SPREAD_DEG = 0.0009

// Groups reports that share (near enough) the same coordinate and arranges
// each group in a small circle around their shared point, so every report
// gets its own clickable pin instead of only the last-drawn one being
// visible. A lone report at a coordinate is left exactly where it is.
function spreadOverlappingReports(reports: ReportRecord[]): (ReportRecord & { _pos: [number, number] })[] {
  const groups = new Map<string, ReportRecord[]>()
  for (const r of reports) {
    const key = `${(r.latitude as number).toFixed(4)},${(r.longitude as number).toFixed(4)}`
    const group = groups.get(key)
    if (group) group.push(r)
    else groups.set(key, [r])
  }

  const result: (ReportRecord & { _pos: [number, number] })[] = []
  for (const group of groups.values()) {
    const [baseLat, baseLon] = [group[0].latitude as number, group[0].longitude as number]
    if (group.length === 1) {
      result.push({ ...group[0], _pos: [baseLat, baseLon] })
      continue
    }
    group.forEach((r, i) => {
      const angle = (2 * Math.PI * i) / group.length
      result.push({
        ...r,
        _pos: [baseLat + CLUSTER_SPREAD_DEG * Math.sin(angle), baseLon + CLUSTER_SPREAD_DEG * Math.cos(angle)],
      })
    })
  }
  return result
}

function buildWindyUrl(lat: number, lon: number, zoom: number) {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    detailLat: String(lat),
    detailLon: String(lon),
    width: '650',
    height: '450',
    zoom: String(zoom),
    level: 'surface',
    overlay: 'wind',
    menu: '',
    message: 'true',
    marker: 'true',
    calendar: 'now',
    pressure: '',
    type: 'map',
    location: 'coordinates',
    metricWind: 'km/h',
    metricTemp: '°C',
    radarRange: '-1',
  })
  return `https://embed.windy.com/embed2.html?${params.toString()}`
}

// Matches the farmer app's map: a sighting older than this is treated as
// resolved and no longer pinned.
const MAX_REPORT_AGE_MS = 14 * 24 * 60 * 60 * 1000

function isRecent(dateSpotted: string): boolean {
  const t = new Date(dateSpotted).getTime()
  // An unparseable date is kept rather than silently dropped.
  return Number.isNaN(t) || Date.now() - t <= MAX_REPORT_AGE_MS
}

function ProvinceMap({ latitude, longitude, label, reports = [] }: ProvinceMapProps) {
  const [mode, setMode] = useState<MapMode>('satellite')
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const pinnableReports = useMemo(() => {
    // Rejected reports are hidden — they were reviewed and ruled out, so
    // they aren't a sighting anyone needs to see on the map.
    const withCoords = reports.filter((r) => r.latitude != null && r.longitude != null && r.status !== 'rejected' && isRecent(r.date_spotted))
    return spreadOverlappingReports(withCoords)
  }, [reports])

  useEffect(() => {
    if (mode !== 'satellite' || !containerRef.current) return

    const map = L.map(containerRef.current, {
      attributionControl: false,
    }).setView([latitude, longitude], 11)
    mapRef.current = map

    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18 },
    ).addTo(map)

    L.circleMarker([latitude, longitude], {
      radius: 8,
      color: '#fff',
      weight: 2,
      fillColor: '#2f6b32',
      fillOpacity: 1,
    })
      .addTo(map)
      .bindPopup(label)

    // Province-wide pins can be far apart, so frame them all (plus the
    // municipality center) instead of staying at the fixed zoom-11 view.
    if (pinnableReports.length > 0) {
      const bounds = L.latLngBounds([[latitude, longitude]])
      pinnableReports.forEach((r) => bounds.extend(r._pos))
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 })
    }

    // Farmer-reported sightings with a known location — colored by the
    // farmer's reported risk level (report.severity), shown to the user as
    // "risk" for vocabulary consistency with the rest of the dashboard.
    // Clicking a pin flies the map in to that exact spot.
    pinnableReports.forEach((report) => {
        const color = SEVERITY_COLOR[report.severity] ?? '#999'
        const pos = report._pos

        // Verified = solid pin (the same set the mobile app counts as active
        // threat zones); pending = faint pin with a dashed risk-colored
        // ring, so unreviewed reports are visibly distinct.
        const isVerified = report.status === 'verified'

        const marker = L.circleMarker(pos, {
          radius: 7,
          color: isVerified ? '#fff' : color,
          weight: 2,
          dashArray: isVerified ? undefined : '3 3',
          fillColor: color,
          fillOpacity: isVerified ? 0.9 : 0.25,
        })
          .addTo(map)
          .bindPopup(
            `<strong>${report.pest_type}</strong><br/>` +
              `${report.severity.charAt(0).toUpperCase()}${report.severity.slice(1)} severity · ${report.status}<br/>` +
              `${report.date_spotted}`,
          )

        marker.on('click', () => {
          map.flyTo(pos, REPORT_ZOOM, { duration: 0.8 })
        })
      })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [mode, latitude, longitude, label, pinnableReports])

  return (
    <div className="province-map">
      <div className="province-map-tabs">
        <button
          type="button"
          className={`province-map-tab${mode === 'satellite' ? ' active' : ''}`}
          onClick={() => setMode('satellite')}
        >
          Satellite
        </button>
        <button
          type="button"
          className={`province-map-tab${mode === 'wind' ? ' active' : ''}`}
          onClick={() => setMode('wind')}
        >
          Wind
        </button>
      </div>

      <div className="province-map-view">
        {mode === 'satellite' ? (
          <div ref={containerRef} className="province-map-canvas" />
        ) : (
          // Plain wind map — no risk-severity pins overlaid, unlike the
          // satellite view. Windy's own embed only ever shows one marker
          // (its detailLat/detailLon pin), fixed on the province center.
          <iframe
            key="wind"
            title="Wind map"
            className="province-map-canvas"
            src={buildWindyUrl(latitude, longitude, 9)}
            frameBorder="0"
          />
        )}
      </div>
    </div>
  )
}

export default ProvinceMap
