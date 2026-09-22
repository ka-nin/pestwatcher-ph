import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Compass } from 'lucide-react';
import { currentLocation } from '../data/mockData';
import './WeatherMap.css';

// Nueva Ecija — zoomed so the whole province is framed, matching the
// admin-web ProvinceMap view (same satellite/wind modes, same tile source).
const PROVINCE_LAT = currentLocation.latitude;
const PROVINCE_LON = currentLocation.longitude;
const PROVINCE_ZOOM = 9;
const REPORT_ZOOM = 14;

const RISK_COLOR = {
  high: '#d64545',
  medium: '#d97b29',
  low: '#3f7d3a',
};

function pillIcon(alert) {
  const color = RISK_COLOR[alert.risk] || RISK_COLOR.low;
  const cityLabel = alert.location.replace(/ CITY$/i, '');
  const km = alert.distance.replace(' away', '');
  return L.divIcon({
    className: 'map-pill-marker',
    html: `
      <span class="map-pill-marker-inner">
        <i style="background:${color}"></i>
        ${cityLabel} (${km})
      </span>
    `,
    iconSize: null,
    iconAnchor: [10, 10],
  });
}

function buildWindyUrl(lat, lon, zoom) {
  const params = new URLSearchParams({
    lat,
    lon,
    detailLat: lat,
    detailLon: lon,
    zoom,
    level: 'surface',
    overlay: 'wind',
    menu: '',
    message: '',
    marker: 'true',
    calendar: 'now',
    pressure: '',
    type: 'map',
    location: 'coordinates',
    detail: '',
    metricWind: 'km/h',
    metricTemp: '°C',
    radarRange: '-1',
  });
  return `https://embed.windy.com/embed2.html?${params.toString()}`;
}

export default function WeatherMap({ fill = false, showControls = fill, alerts = [] }) {
  const [mode, setMode] = useState('satellite');
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  const pinnableAlerts = useMemo(
    () => alerts.filter((a) => a.latitude != null && a.longitude != null),
    [alerts]
  );

  useEffect(() => {
    if (mode !== 'satellite' || !containerRef.current) return;

    const map = L.map(containerRef.current, { attributionControl: false }).setView(
      [PROVINCE_LAT, PROVINCE_LON],
      PROVINCE_ZOOM
    );
    mapRef.current = map;

    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18 }
    ).addTo(map);

    pinnableAlerts.forEach((alert) => {
      const pos = [alert.latitude, alert.longitude];
      const marker = L.marker(pos, { icon: pillIcon(alert) }).addTo(map);
      marker.on('click', () => {
        map.flyTo(pos, REPORT_ZOOM, { duration: 0.8 });
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [mode, pinnableAlerts]);

  return (
    <div className={`weather-map${fill ? ' weather-map-fill' : ''}`}>
      <div className="weather-map-frame">
        {mode === 'satellite' ? (
          <div ref={containerRef} className="weather-map-canvas" />
        ) : (
          // Plain wind map — no risk-severity pins overlaid, unlike the
          // satellite view. Windy's own embed only ever shows one marker
          // (its detailLat/detailLon pin), fixed on the province center.
          <iframe
            key="wind"
            title="Nueva Ecija wind map"
            src={buildWindyUrl(PROVINCE_LAT, PROVINCE_LON, PROVINCE_ZOOM)}
            loading="lazy"
            allowFullScreen
          />
        )}
        <span className="weather-map-compass">
          <Compass size={16} />
        </span>
      </div>

      {showControls && (
        <div className="weather-map-controls">
          <button
            className={`weather-map-toggle${mode === 'satellite' ? ' active' : ''}`}
            onClick={() => setMode('satellite')}
          >
            Satellite
          </button>
          <button
            className={`weather-map-toggle${mode === 'wind' ? ' active' : ''}`}
            onClick={() => setMode('wind')}
          >
            Wind
          </button>
        </div>
      )}
    </div>
  );
}
