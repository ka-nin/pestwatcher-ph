import { useState } from 'react';
import { Wind, Thermometer } from 'lucide-react';
import './WeatherMap.css';

// Central Luzon default view — centered near Nueva Ecija/Tarlac so the
// region's rice-growing provinces are framed on first load.
const DEFAULT_LAT = 15.48;
const DEFAULT_LON = 120.9;
const DEFAULT_ZOOM = 8;

// Windy's free embed widget takes overlay/zoom/lat/lon as URL params and
// ships its own zoom + pan controls out of the box. We only expose the
// overlay switch (heatmap vs wind) to farmers — Windy's own UI chrome
// (search, menus, etc.) is hidden via the embed's minimal params where
// possible; the widget still allows pinch/scroll zoom natively.
const OVERLAYS = [
  { id: 'temp', label: 'Heatmap', icon: Thermometer, windyOverlay: 'temp' },
  { id: 'wind', label: 'Wind Map', icon: Wind, windyOverlay: 'wind' },
];

function buildWindyUrl(overlay) {
  const params = new URLSearchParams({
    lat: DEFAULT_LAT,
    lon: DEFAULT_LON,
    detailLat: DEFAULT_LAT,
    detailLon: DEFAULT_LON,
    zoom: DEFAULT_ZOOM,
    level: 'surface',
    overlay,
    menu: '',
    message: '',
    marker: '',
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

export default function WeatherMap({ fill = false }) {
  const [overlay, setOverlay] = useState('temp');

  return (
    <div className={`weather-map${fill ? ' weather-map-fill' : ''}`}>
      <div className="weather-map-frame">
        <iframe
          key={overlay}
          title="Central Luzon weather map"
          src={buildWindyUrl(overlay)}
          loading="lazy"
          allowFullScreen
        />
      </div>

      <div className="weather-map-controls">
        {OVERLAYS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`weather-map-toggle${overlay === id ? ' active' : ''}`}
            onClick={() => setOverlay(id)}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
