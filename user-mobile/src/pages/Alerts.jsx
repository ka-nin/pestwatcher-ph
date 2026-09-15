import { MapPin, SlidersHorizontal } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import RiskBadge from '../components/RiskBadge';
import WeatherMap from '../components/WeatherMap';
import { currentLocation } from '../data/mockData';
import { useReports } from '../hooks/useReports';
import './Alerts.css';

export default function Alerts() {
  const navigate = useNavigate();
  const { reports, loading, error } = useReports();

  return (
    <div className="alerts-screen">
      <div className="alerts-header">
        <div>
          <h1>REGIONAL ALERTS</h1>
          <p>
            {currentLocation.province} &amp; Nearby Areas
          </p>
        </div>
        <button className="alerts-header-filter" aria-label="Filter alerts">
          <SlidersHorizontal size={16} />
        </button>
      </div>

      <div className="alerts-body">
        <div className="alerts-map">
          <WeatherMap alerts={reports} />
          <div className="alerts-map-footer">
            <span>
              {loading
                ? 'Loading threat zones...'
                : `Showing ${reports.length} active threat zone${reports.length === 1 ? '' : 's'} nearby`}
            </span>
            <button onClick={() => navigate('/alerts/map')}>Expand Map</button>
          </div>
        </div>

        <div className="alerts-list-header">
          <h2>ACTIVE THREATS</h2>
          <span>{loading ? '...' : 'Updated just now'}</span>
        </div>

        {error && <p className="alerts-error">{error}</p>}

        {!loading && reports.length === 0 && !error && (
          <p className="alerts-empty">Walang naitalang sightings sa paligid ngayon.</p>
        )}

        <div className="alerts-list">
          {reports.map((alert) => (
            <article key={alert.id} className={`alert-card risk-${alert.risk}`}>
              <div className="alert-card-top">
                <RiskBadge level={alert.risk} label={alert.riskLabel} />
                {alert.status === 'verified' && <span className="alert-verified-badge">LGU Verified</span>}
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
