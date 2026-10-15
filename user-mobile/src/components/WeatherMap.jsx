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

// Served from /public/geo as a plain fetch rather than a bundled import —
// mirrors admin-web's ProvinceMap.tsx, including the same source file, so
// both apps draw the identical provincial boundary. Covers all seven
// Central Luzon provinces, not just Nueva Ecija, for the same reason.
const PROVINCE_BOUNDARIES_URL = '/geo/central_luzon_provinces.json';

// Mirrors --color-accent-red/-orange/-primary in index.css — kept as literal
// hex here (not var()) since these values are injected into Leaflet divIcon/
// popup HTML strings, which render outside this component's own stylesheet
// cascade.
const RISK_COLOR = {
  high: '#d64545',
  medium: '#d97b29',
  low: '#3f7d3a',
};

// How far apart (in degrees) to nudge pins that would otherwise sit on
// exactly the same spot — several reports from the same municipality often
// carry that municipality's fixed coordinates rather than a real per-sighting
// GPS pin, so without this every later pin silently hides behind the first
// one drawn. Mirrors admin-web's ProvinceMap.tsx fix for the same issue.
const CLUSTER_SPREAD_DEG = 0.0009;

function spreadOverlappingAlerts(alerts) {
  const groups = new Map();
  for (const a of alerts) {
    const key = `${a.latitude.toFixed(4)},${a.longitude.toFixed(4)}`;
    const group = groups.get(key);
    if (group) group.push(a);
    else groups.set(key, [a]);
  }

  const result = [];
  for (const group of groups.values()) {
    const [baseLat, baseLon] = [group[0].latitude, group[0].longitude];
    if (group.length === 1) {
      result.push({ ...group[0], _pos: [baseLat, baseLon] });
      continue;
    }
    group.forEach((a, i) => {
      const angle = (2 * Math.PI * i) / group.length;
      result.push({
        ...a,
        _pos: [baseLat + CLUSTER_SPREAD_DEG * Math.sin(angle), baseLon + CLUSTER_SPREAD_DEG * Math.cos(angle)],
      });
    });
  }
  return result;
}

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

function popupHtml(alert) {
  const color = RISK_COLOR[alert.risk] || RISK_COLOR.low;
  return `
    <div class="map-report-popup">
      <div class="map-report-popup-title">${alert.pestName}</div>
      <div class="map-report-popup-risk" style="color:${color}">${alert.riskLabel}</div>
      <div class="map-report-popup-meta">${alert.location} · ${alert.date}</div>
      ${alert.description ? `<div class="map-report-popup-desc">${alert.description}</div>` : ''}
    </div>
  `;
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
  const [boundary, setBoundary] = useState(null);

  // Fetched once on mount — the file covers every province, so there is no
  // per-farmer variant to re-fetch, and currentLocation.province doesn't
  // change within a session.
  useEffect(() => {
    let cancelled = false;
    fetch(PROVINCE_BOUNDARIES_URL)
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        const match = data.features.find(
          (f) => f.properties.province.toLowerCase() === currentLocation.province.toLowerCase()
        );
        setBoundary(match ?? null);
      })
      .catch(() => {
        // Quiet degradation — the pins and province center still work
        // without the outline.
        if (!cancelled) setBoundary(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pinnableAlerts = useMemo(() => {
    const withCoords = alerts.filter((a) => a.latitude != null && a.longitude != null);
    return spreadOverlappingAlerts(withCoords);
  }, [alerts]);

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

    // The province outline, drawn first so every pin layers on top of it.
    // Dashed and unfilled — a coverage boundary, not a risk zone — matching
    // admin-web's ProvinceMap.tsx styling exactly.
    let boundaryLayer = null;
    if (boundary) {
      boundaryLayer = L.geoJSON(boundary, {
        style: {
          color: '#ffd166',
          weight: 2.5,
          opacity: 0.9,
          fillOpacity: 0,
          dashArray: '6 5',
        },
        interactive: false,
      }).addTo(map);
    }

    // Frame the whole covered area: the province outline when there's one,
    // widened to include every pin, which can sit right at the edge.
    const bounds = boundaryLayer ? boundaryLayer.getBounds() : L.latLngBounds([[PROVINCE_LAT, PROVINCE_LON]]);
    bounds.extend([PROVINCE_LAT, PROVINCE_LON]);
    pinnableAlerts.forEach((a) => bounds.extend(a._pos));
    if (boundaryLayer || pinnableAlerts.length > 0) {
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
    }

    pinnableAlerts.forEach((alert) => {
      const pos = alert._pos;
      const marker = L.marker(pos, { icon: pillIcon(alert) })
        .addTo(map)
        .bindPopup(popupHtml(alert));
      marker.on('click', () => {
        map.flyTo(pos, REPORT_ZOOM, { duration: 0.8 });
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [mode, pinnableAlerts, boundary]);

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
        {showControls && mode === 'satellite' && boundary && (
          <span className="weather-map-boundary-legend">
            <span className="weather-map-boundary-swatch" />
            {currentLocation.province} boundary
          </span>
        )}
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
