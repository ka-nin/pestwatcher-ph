import { MapPin, SlidersHorizontal } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import RiskBadge from '../components/RiskBadge';
import WeatherMap from '../components/WeatherMap';
import { currentLocation } from '../data/mockData';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { useReports } from '../hooks/useReports';
import { useMunicipalityRisk } from '../hooks/useMunicipalityRisk';
import './Alerts.css';

const RISK_LABEL_KEY = { Low: 'riskLabelLow', Medium: 'riskLabelMedium', High: 'riskLabelHigh' };

function riskLabelKeyFor(severity) {
  if (!severity) return 'riskLabelLow';
  const capitalized = severity[0].toUpperCase() + severity.slice(1).toLowerCase();
  return RISK_LABEL_KEY[capitalized] || 'riskLabelLow';
}

export default function Alerts() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLanguage();
  const { reports, loading, error } = useReports();
  const { rows: riskRows, loading: riskLoading, error: riskError } = useMunicipalityRisk(user?.municipality);

  return (
    <div className="alerts-screen">
      <div className="alerts-header hero-surface">
        <div>
          <h1>{t('alertsTitle')}</h1>
          <p>
            {currentLocation.province} {t('alertsSubtitle')}
          </p>
        </div>
        <button className="alerts-header-filter" aria-label={t('alertsFilterLabel')}>
          <SlidersHorizontal size={16} />
        </button>
      </div>

      <div className="alerts-body">
        <div className="alerts-map">
          <WeatherMap alerts={reports} />
          <div className="alerts-map-footer">
            <span>
              {loading
                ? t('alertsMapLoading')
                : `${reports.length} ${t('alertsMapShowing')}${reports.length === 1 ? '' : 's'}`}
            </span>
            <button onClick={() => navigate('/alerts/map')}>{t('alertsExpandMap')}</button>
          </div>
        </div>

        <div className="alerts-list-header">
          <h2>{t('alertsMunicipalityRiskTitle')}</h2>
          <span>{riskLoading ? '...' : t('alertsLive')}</span>
        </div>

        {riskError && <p className="alerts-error">{riskError}</p>}

        {!riskLoading && riskRows.length === 0 && !riskError && (
          <p className="alerts-empty">{t('alertsNoRiskData')}</p>
        )}

        {riskRows.length > 0 && (
          <div className="municipality-risk-list">
            {riskRows.map((row) => (
              <div
                key={row.municipality}
                className={`municipality-risk-row${row.municipality === user?.municipality ? ' is-own' : ''}`}
              >
                <span className="municipality-risk-name">
                  {row.municipality}
                  {row.municipality === user?.municipality && (
                    <span className="municipality-risk-you">{t('alertsYouAreHere')}</span>
                  )}
                </span>
                {row.risk ? (
                  <RiskBadge level={row.risk.toLowerCase()} label={t(RISK_LABEL_KEY[row.risk] || 'riskLabelLow')} />
                ) : (
                  <span className="municipality-risk-na">{t('alertsNa')}</span>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="alerts-list-header">
          <h2>{t('alertsActiveThreats')}</h2>
          <span>{loading ? '...' : t('alertsUpdatedNow')}</span>
        </div>

        {error && <p className="alerts-error">{error}</p>}

        {!loading && reports.length === 0 && !error && (
          <p className="alerts-empty">{t('alertsEmpty')}</p>
        )}

        <div className="alerts-list">
          {reports.map((alert) => (
            <article key={alert.id} className={`alert-card risk-${alert.risk}`}>
              <div className="alert-card-top">
                <RiskBadge level={alert.risk} label={t(riskLabelKeyFor(alert.risk))} />
                {alert.status === 'verified' && (
                  <span className="alert-verified-badge">{t('alertsLguVerified')}</span>
                )}
                <span className="alert-date">{alert.date}</span>
              </div>

              <h3>{alert.pestName}</h3>
              <p className="alert-scientific">{alert.scientificName}</p>

              <p className="alert-location">
                <MapPin size={13} />
                <span className="alert-location-name">{alert.location}</span>
                <span className="alert-distance">{alert.distance}</span>
              </p>

              <p className="alert-desc">{alert.description}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
