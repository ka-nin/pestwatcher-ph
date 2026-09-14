import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import WeatherMap from '../components/WeatherMap';
import { currentLocation } from '../data/mockData';
import './MapExpanded.css';

export default function MapExpanded() {
  const navigate = useNavigate();

  return (
    <div className="map-expanded-screen">
      <div className="map-expanded-header">
        <div>
          <h1>Weather Map</h1>
          <p>
            {currentLocation.province}, {currentLocation.region}
          </p>
        </div>
        <button className="map-expanded-close" onClick={() => navigate(-1)} aria-label="Close map">
          <X size={20} />
        </button>
      </div>

      <div className="map-expanded-body">
        <WeatherMap fill />
      </div>
    </div>
  );
}
