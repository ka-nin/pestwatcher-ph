import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './ProvinceMap.css'

interface ProvinceMapProps {
  latitude: number
  longitude: number
  label: string
}

type MapMode = 'satellite' | 'wind'

function ProvinceMap({ latitude, longitude, label }: ProvinceMapProps) {
  const [mode, setMode] = useState<MapMode>('satellite')
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)

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

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [mode, latitude, longitude, label])

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
          <iframe
            key="wind"
            title="Wind map"
            className="province-map-canvas"
            src={`https://embed.windy.com/embed2.html?lat=${latitude}&lon=${longitude}&detailLat=${latitude}&detailLon=${longitude}&width=650&height=450&zoom=9&level=surface&overlay=wind&menu=&message=true&marker=true&calendar=now&pressure=&type=map&location=coordinates&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1`}
            frameBorder="0"
          />
        )}
      </div>
    </div>
  )
}

export default ProvinceMap
