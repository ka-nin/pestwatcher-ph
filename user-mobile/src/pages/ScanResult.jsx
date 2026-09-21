import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { X, RotateCcw, Sprout } from 'lucide-react';
import RiskBadge from '../components/RiskBadge';
import { pestGuide, etlThresholds } from '../data/mockData';
import { PestHeroMedia } from '../data/pestIcons';
import { fetchPestForecast, fetchPestForecastTrajectory } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './GuideDetail.css';
import './ScanResult.css';

const RISK_LABEL_FIL = {
  low: 'Mababang Panganib',
  medium: 'Katamtamang Panganib',
  high: 'Mataas na Panganib',
};

const RISK_SUMMARY_FIL = {
  low: 'Mababa ang inaasahang panganib sa loob ng 14 araw. Ipagpatuloy ang normal na pagmamanman.',
  medium:
    'May pagtaas ng panganib na inaasahan sa loob ng 14 araw. Bantayan ang bukid at maghanda ng aksyon.',
  high: 'Mataas ang inaasahang panganib sa loob ng 14 araw. Inirerekomenda ang agarang interbensyon.',
};

const RISK_HERO_GRADIENT = {
  low: 'radial-gradient(120% 140% at 100% 0%, #6ba362 0%, #3f7d3a 32%, #2f5f2c 68%, #1f4020 100%)',
  medium: 'radial-gradient(120% 140% at 100% 0%, #ddc066 0%, #c9a227 32%, #9a7a1c 68%, #6b5312 100%)',
  high: 'radial-gradient(120% 140% at 100% 0%, #e37c6e 0%, #d64545 32%, #a3312f 68%, #6e211f 100%)',
};

const GUIDE_ID_BY_PEST = { BPH: 'bph', RSB: 'stem-borer' };
const GROWTH_BUCKET = {
  Seedling: 'Vegetative',
  Tillering: 'Vegetative',
  Elongation: 'Vegetative',
  Panicle: 'Reproductive',
  Flowering: 'Reproductive',
  Ripening: 'Reproductive',
};
const RISK_RANK = { Low: 0, Medium: 1, High: 2 };

const DAY_NAMES_FIL = { Mon: 'Lun', Tue: 'Mar', Wed: 'Miy', Thu: 'Huw', Fri: 'Biy', Sat: 'Sab', Sun: 'Lin' };

export default function ScanResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, growthStage } = useAuth();

  // Real result from the just-completed /api/inference/image call, passed
  // via navigation state from ScanCapture.
  const inference = location.state?.inference;

  const [forecast, setForecast] = useState(null);
  const [trajectory, setTrajectory] = useState(null);
  const [resolvedPest, setResolvedPest] = useState(null);
  const [loadingForecast, setLoadingForecast] = useState(true);
  const [forecastError, setForecastError] = useState('');

  // The photo classification (what the camera saw) and the weather-based
  // forecast (what the model expects over the next 14 days) are two
  // genuinely separate signals — this app doesn't have a model that turns
  // a photo into a pest count, and the BiLSTM forecast never takes a photo
  // as input (see the ml/resnet vs ml/bilstm pipelines). Both are shown
  // honestly side by side rather than merged into one fabricated number.
  useEffect(() => {
    if (!inference || inference.status !== 'ok' || !user) return;
    let cancelled = false;
    setLoadingForecast(true);
    setForecastError('');

    const detectedPest = inference.pest_detected?.startsWith('BPH')
      ? 'BPH'
      : inference.pest_detected?.startsWith('RSB')
        ? 'RSB'
        : null;

    async function loadForecast() {
      try {
        if (detectedPest) {
          const [live, traj] = await Promise.all([
            fetchPestForecast(user.municipality, detectedPest, growthStage),
            fetchPestForecastTrajectory(user.municipality, detectedPest, growthStage, 14),
          ]);
          if (cancelled) return;
          setResolvedPest(detectedPest);
          setForecast(live.status === 'ok' ? live : null);
          setTrajectory(traj.status === 'ok' ? traj.points : []);
        } else {
          // No specific pest detected (e.g. "Healthy") — fall back to
          // whichever of BPH/RSB currently carries the worse forecast for
          // this farm, same logic Home's dashboard card uses.
          const [bph, rsb] = await Promise.all([
            fetchPestForecast(user.municipality, 'BPH', growthStage),
            fetchPestForecast(user.municipality, 'RSB', growthStage),
          ]);
          if (cancelled) return;
          const candidates = [
            { pest: 'BPH', ...bph },
            { pest: 'RSB', ...rsb },
          ].filter((f) => f.status === 'ok');
          const worst = candidates.sort((a, b) => (RISK_RANK[b.risk_level] ?? -1) - (RISK_RANK[a.risk_level] ?? -1))[0];
          setResolvedPest(worst?.pest || 'BPH');
          setForecast(worst || null);
          if (worst) {
            const traj = await fetchPestForecastTrajectory(user.municipality, worst.pest, growthStage, 14);
            if (!cancelled) setTrajectory(traj.status === 'ok' ? traj.points : []);
          }
        }
      } catch (err) {
        if (!cancelled) setForecastError(err.message || 'Hindi makuha ang live forecast.');
      } finally {
        if (!cancelled) setLoadingForecast(false);
      }
    }

    loadForecast();
    return () => {
      cancelled = true;
    };
  }, [inference, user, growthStage]);

  if (!inference || inference.status !== 'ok') {
    return (
      <div className="guide-detail-screen scan-result-unavailable">
        <button className="guide-detail-close scan-result-unavailable-close" onClick={() => navigate('/home')} aria-label="Close">
          <X size={18} />
        </button>
        <div className="scan-result-unavailable-body">
          <h1>Hindi pa handa ang AI model</h1>
          <p>
            {inference?.message ||
              'Ang larawan ay na-save na para sa training, pero wala pang trained na image classification model. Subukan ulit sa susunod.'}
          </p>
          <button className="scan-result-rescan-btn" onClick={() => navigate('/scan')}>
            Scan Ulit
          </button>
        </div>
      </div>
    );
  }

  const photoDetected = inference.pest_detected && inference.pest_detected !== 'Healthy';
  const guideId = resolvedPest ? GUIDE_ID_BY_PEST[resolvedPest] : 'bph';
  const entry = pestGuide.find((p) => p.id === guideId) || pestGuide[0];

  const forecastRisk = forecast?.risk_level?.toLowerCase() || null;
  const bucket = GROWTH_BUCKET[growthStage] || 'Vegetative';
  const stageThresholds = etlThresholds[guideId]?.[bucket];
  const measurement = forecast?.predicted_value ?? null;

  return (
    <div className="guide-detail-screen">
      <div
        className="guide-detail-hero"
        style={{ background: forecastRisk ? RISK_HERO_GRADIENT[forecastRisk] : RISK_HERO_GRADIENT.medium }}
      >
        <PestHeroMedia id={entry.id} />
        <div className="guide-detail-hero-scrim scan-result-hero-scrim" />
        <button className="scan-result-rescan-top" onClick={() => navigate('/scan')} aria-label="Scan Ulit">
          <RotateCcw size={16} />
        </button>
        <button className="guide-detail-close" onClick={() => navigate('/home')} aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="guide-detail-sheet">
        {/* Signal 1: what the photo itself showed */}
        <section className="scan-result-signal">
          <span className="scan-result-signal-label">Mula sa Larawan</span>
          <div className="scan-result-confidence">
            <span className={`scan-result-photo-chip${photoDetected ? ' detected' : ''}`}>
              {inference.pest_detected || 'Walang natukoy'}
            </span>
            <span>{Math.round((inference.confidence ?? 0) * 100)}% confidence</span>
          </div>
        </section>

        <h1>{entry.name}</h1>
        <p className="guide-detail-fil">
          {entry.nameFil} <em>({entry.scientificName})</em>
        </p>

        <span className="scan-result-etl-tag scan-result-stage-tag">
          <Sprout size={13} /> {growthStage} ({bucket})
        </span>

        {/* Signal 2: the live, weather-based forecast for this farm — not derived from the photo */}
        <section className="scan-result-signal scan-result-signal-forecast">
          <span className="scan-result-signal-label">Live na Forecast (Batay sa Panahon)</span>

          {loadingForecast && <p className="scan-result-summary">Kinukuha ang live forecast...</p>}
          {forecastError && <p className="scan-result-summary">{forecastError}</p>}

          {!loadingForecast && forecast && forecastRisk && (
            <>
              <div className="scan-result-confidence">
                <RiskBadge level={forecastRisk} label={RISK_LABEL_FIL[forecastRisk]} />
                {forecast.adjusted_by_reports && (
                  <span>Naaayon sa {forecast.verified_report_count} verified na ulat</span>
                )}
              </div>
              <p className="scan-result-summary">{RISK_SUMMARY_FIL[forecastRisk]}</p>
            </>
          )}

          {!loadingForecast && !forecast && (
            <p className="scan-result-summary">
              Hindi pa available ang BiLSTM forecast model para sa {resolvedPest || 'peste na ito'} sa lugar na ito.
            </p>
          )}
        </section>

        {trajectory && trajectory.length > 0 && (
          <section>
            <h2>14-ARAW NA PAGTATAYA NG PANGANIB</h2>
            <div className="forecast-grid">
              {trajectory.map((day) => {
                const d = new Date(day.date);
                const dayFil = DAY_NAMES_FIL[d.toLocaleDateString('en-US', { weekday: 'short' })];
                return (
                  <div key={day.date} className={`forecast-day risk-${day.risk_level.toLowerCase()}`}>
                    <span className="forecast-day-name">{dayFil}</span>
                    <span className="forecast-day-date">
                      {d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="forecast-legend">
              <span><i className="risk-low" /> Mababa</span>
              <span><i className="risk-medium" /> Katamtaman</span>
              <span><i className="risk-high" /> Mataas</span>
            </div>
          </section>
        )}

        {stageThresholds && measurement != null && (
          <section className="scan-result-etl">
            <div className="scan-result-etl-measurement">
              <span className="scan-result-etl-value">
                {measurement.toFixed(1)}
                <small>{stageThresholds.unit}</small>
              </span>
              <span className="scan-result-etl-metric-label">{stageThresholds.metricLabel} (BiLSTM forecast)</span>
            </div>
            <div className="etl-scale">
              <div className="etl-scale-track">
                <div className={`etl-scale-fill risk-${forecastRisk}`} />
                <div
                  className="etl-scale-marker"
                  style={{
                    left: `${Math.min(100, (measurement / (stageThresholds.medium * 1.4)) * 100)}%`,
                  }}
                />
              </div>
              <div className="etl-scale-labels">
                <span>Mababa (&lt;{stageThresholds.low})</span>
                <span>Katamtaman ({stageThresholds.low}–{stageThresholds.medium})</span>
                <span>Mataas (&gt;{stageThresholds.medium})</span>
              </div>
              <p className="etl-scale-note">
                Batay sa Economic Threshold Level (ETL) ng PhilRice at DA-RCPC para sa {entry.name} sa{' '}
                {bucket === 'Vegetative' ? 'vegetative' : 'reproductive'} na yugto.
              </p>
            </div>
          </section>
        )}

        <section>
          <h2>TUNGKOL SA PESTENG ITO</h2>
          <p>{entry.description}</p>
        </section>

        <section>
          <h2>MGA PALATANDAAN</h2>
          <ul>
            {entry.signs.map((sign) => (
              <li key={sign}>{sign}</li>
            ))}
          </ul>
        </section>

        <section>
          <h2>INIREREKOMENDANG AKSYON</h2>
          <ul>
            {entry.prevention.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
