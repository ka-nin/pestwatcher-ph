import { MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import RiskBadge from '../components/RiskBadge';
import WeatherMap from '../components/WeatherMap';
import { currentLocation, regionalAlerts } from '../data/mockData';
import './Alerts.css';

export default function Alerts() {
  const navigate = useNavigate();

  return (
    <div className="alerts-screen">
      <div className="alerts-header">
        <h1>REGIONAL ALERTS</h1>
        <p>
          {currentLocation.province} &amp; Nearby Areas
        </p>
      </div>

      <div className="alerts-body">
        <div className="alerts-map">
          <WeatherMap />
          <div className="alerts-map-footer">
            <span>Showing 3 active threat zones nearby</span>
            <button onClick={() => navigate('/alerts/map')}>Expand Map</button>
          </div>
        </div>

        <div className="alerts-list-header">
          <h2>ACTIVE THREATS</h2>
          <span>Updated 5m ago</span>
        </div>

        <div className="alerts-list">
          {regionalAlerts.map((alert) => (
            <article key={alert.id} className={`alert-card risk-${alert.risk}`}>
              <div className="alert-card-top">
                <RiskBadge level={alert.risk} label={alert.riskLabel} />
                <span className="alert-distance">{alert.distance}</span>
                <span className="alert-date">{alert.date}</span>
              </div>
              <h3>{alert.pestName}</h3>
              <p className="alert-location">
                <MapPin size={12} /> {alert.location} &middot; <em>{alert.scientificName}</em>
              </p>
              <p className="alert-desc">{alert.description}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
