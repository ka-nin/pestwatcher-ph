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

function ProvinceMap({ latitude, longitude, label, reports = [] }: ProvinceMapProps) {
  const [mode, setMode] = useState<MapMode>('satellite')
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const pinnableReports = useMemo(
    () => reports.filter((r) => r.latitude != null && r.longitude != null),
    [reports],
  )

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

    // Farmer-reported sightings with a known location — colored by severity,
    // clicking one flies the map in to that exact spot.
    pinnableReports.forEach((report) => {
        const color = SEVERITY_COLOR[report.severity] ?? '#999'
        const pos: [number, number] = [report.latitude as number, report.longitude as number]

        const marker = L.circleMarker(pos, {
          radius: 7,
          color: '#fff',
          weight: 2,
          fillColor: color,
          fillOpacity: 0.9,
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
