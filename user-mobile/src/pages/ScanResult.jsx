import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { X, RotateCcw, Sprout } from 'lucide-react';
import RiskBadge from '../components/RiskBadge';
import { pestGuide, etlThresholds, classifyRisk, scanDetectionByRisk } from '../data/mockData';
import { PestHeroMedia } from '../data/pestIcons';
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

// Matches the risk gradients used on Home's hero card so a High-risk scan
// result and a High-risk dashboard card read as the same visual language.
const RISK_HERO_GRADIENT = {
  low: 'radial-gradient(120% 140% at 100% 0%, #6ba362 0%, #3f7d3a 32%, #2f5f2c 68%, #1f4020 100%)',
  medium: 'radial-gradient(120% 140% at 100% 0%, #ddc066 0%, #c9a227 32%, #9a7a1c 68%, #6b5312 100%)',
  high: 'radial-gradient(120% 140% at 100% 0%, #e37c6e 0%, #d64545 32%, #a3312f 68%, #6e211f 100%)',
};

// Maps the backend's ResNet pest codes to the local pest encyclopedia entry.
const PEST_ID_BY_CODE = { BPH: 'bph', RSB: 'stem-borer' };

const BACKEND_RISK_TO_LOCAL = { Low: 'low', Medium: 'medium', High: 'high' };

function UnavailableScreen({ title, message, onClose, onRescan }) {
  return (
    <div className="guide-detail-screen scan-result-unavailable">
      <button className="guide-detail-close scan-result-unavailable-close" onClick={onClose} aria-label="Close">
        <X size={18} />
      </button>
      <div className="scan-result-unavailable-body">
        <h1>{title}</h1>
        <p>{message}</p>
        <button className="scan-result-rescan-btn" onClick={onRescan}>
          Scan Ulit
        </button>
      </div>
    </div>
  );
}

export default function ScanResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  // Real result from the just-completed /api/inference/image call, passed
  // via navigation state from ScanCapture. Undefined if this screen was
  // reached directly (e.g. via a bookmark or the ?risk= design-testing path).
  const inference = location.state?.inference;

  const closeToHome = () => navigate('/home');
  const rescan = () => navigate('/scan');

  if (inference && inference.status === 'model_not_loaded') {
    return (
      <UnavailableScreen
        title="Hindi pa handa ang AI model"
        message={
          inference.message ||
          'Ang larawan ay na-save na para sa training, pero wala pang trained na image classification model. Subukan ulit sa susunod.'
        }
        onClose={closeToHome}
        onRescan={rescan}
      />
    );
  }

  if (inference && inference.status === 'no_pest_detected') {
    return (
      <UnavailableScreen
        title="Walang natukoy na peste"
        message={
          inference.message ||
          'Walang nakitang Brown Planthopper o Rice Stem Borer sa larawang ito. Subukan ulit nang mas malapit sa peste.'
        }
        onClose={closeToHome}
        onRescan={rescan}
      />
    );
  }

  // Real, successful detection. entry/risk/forecast all come straight from
  // the backend response instead of the mock scenarios below.
  if (inference && inference.status === 'ok') {
    const entry = pestGuide.find((p) => p.id === PEST_ID_BY_CODE[inference.pest_detected]) || pestGuide[0];
    const forecastPoints = inference.forecast?.points || [];
    // The trajectory's first point is "today" — used for the hero risk
    // badge/gradient, same as how the mock version reads today's measurement.
    const todayRisk = forecastPoints[0]
      ? BACKEND_RISK_TO_LOCAL[forecastPoints[0].risk_level] || 'low'
      : 'low';

    return (
      <div className="guide-detail-screen">
        <div className="guide-detail-hero" style={{ background: RISK_HERO_GRADIENT[todayRisk] }}>
          <PestHeroMedia id={entry.id} />
          <div className="guide-detail-hero-scrim scan-result-hero-scrim" />
          <button className="scan-result-rescan-top" onClick={rescan} aria-label="Scan Ulit">
            <RotateCcw size={16} />
          </button>
          <button className="guide-detail-close" onClick={closeToHome} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="guide-detail-sheet">
          <div className="scan-result-confidence">
            <RiskBadge level={todayRisk} label={RISK_LABEL_FIL[todayRisk]} />
            <span>{Math.round(inference.confidence * 100)}% confidence</span>
          </div>

          <h1>{entry.name}</h1>
          <p className="guide-detail-fil">
            {entry.nameFil} <em>({entry.scientificName})</em>
          </p>

          <p className="scan-result-summary">{RISK_SUMMARY_FIL[todayRisk]}</p>

          {forecastPoints.length > 0 && (
            <section>
              <h2>14-ARAW NA PAGTATAYA NG PANGANIB</h2>
              <div className="forecast-grid">
                {forecastPoints.map((point) => {
                  const day = new Date(point.date);
                  const risk = BACKEND_RISK_TO_LOCAL[point.risk_level] || 'low';
                  return (
                    <div key={point.date} className={`forecast-day risk-${risk}`}>
                      <span className="forecast-day-name">
                        {day.toLocaleDateString('en-US', { weekday: 'short' })}
                      </span>
                      <span className="forecast-day-date">{day.getDate()}</span>
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

          {!inference.forecast && (
            <p className="scan-result-summary">
              Walang available na 14-araw na forecast — kulang ang lokasyon o growth stage ng account.
            </p>
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

  // No real inference result — either this screen was opened directly, or
  // we're previewing a risk state for design/testing via ?risk=. Uses the
  // mock scanDetectionByRisk scenarios, which include the richer
  // ETL-measurement section the real backend response doesn't have yet.
  const scenario = searchParams.get('risk');
  const scanDetection =
    (scenario && scanDetectionByRisk[scenario]) || scanDetectionByRisk.medium;
  const { pestId, cropStage, cropStageFil, measurement, confidence, forecast } = scanDetection;

  const entry = pestGuide.find((p) => p.id === pestId) || pestGuide[0];
  const pestThresholds = etlThresholds[pestId];
  const stageThresholds = pestThresholds?.[cropStage];
  const risk = classifyRisk(pestId, cropStage, measurement);
  // A stage can override the pest-level unit/label (e.g. Rice Stem Borer's
  // Reproductive stage is measured in % white ears instead of dead hearts).
  const unit = stageThresholds?.unit || pestThresholds?.unit || '';
  const metricLabel = stageThresholds?.metricLabel || pestThresholds?.metricLabel || 'Sukatan';

  return (
    <div className="guide-detail-screen">
      <div className="guide-detail-hero" style={{ background: RISK_HERO_GRADIENT[risk] }}>
        <PestHeroMedia id={entry.id} />
        <div className="guide-detail-hero-scrim scan-result-hero-scrim" />
        <button className="scan-result-rescan-top" onClick={rescan} aria-label="Scan Ulit">
          <RotateCcw size={16} />
        </button>
        <button className="guide-detail-close" onClick={closeToHome} aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="guide-detail-sheet">
        {/* Summary report */}
        <div className="scan-result-confidence">
          <RiskBadge level={risk} label={RISK_LABEL_FIL[risk]} />
          <span>{Math.round(confidence * 100)}% confidence</span>
        </div>

        <h1>{entry.name}</h1>
        <p className="guide-detail-fil">
          {entry.nameFil} <em>({entry.scientificName})</em>
        </p>

        <p className="scan-result-summary">{RISK_SUMMARY_FIL[risk]}</p>

        <span className="scan-result-etl-tag scan-result-stage-tag">
          <Sprout size={13} /> {cropStageFil}
        </span>

        {/* 14-day daily risk forecast */}
        <section>
          <h2>14-ARAW NA PAGTATAYA NG PANGANIB</h2>
          <div className="forecast-grid">
            {forecast.map((day, i) => (
              <div key={i} className={`forecast-day risk-${day.risk}`}>
                <span className="forecast-day-name">{day.dayFil}</span>
                <span className="forecast-day-date">{day.dateLabel}</span>
              </div>
            ))}
          </div>
          <div className="forecast-legend">
            <span><i className="risk-low" /> Mababa</span>
            <span><i className="risk-medium" /> Katamtaman</span>
            <span><i className="risk-high" /> Mataas</span>
          </div>
        </section>

        {/* ETL basis for today's reading */}
        {stageThresholds && (
          <section className="scan-result-etl">
            <div className="scan-result-etl-measurement">
              <span className="scan-result-etl-value">
                {measurement}
                <small>{unit}</small>
              </span>
              <span className="scan-result-etl-metric-label">{metricLabel} (ngayong araw)</span>
            </div>
            <div className="etl-scale">
              <div className="etl-scale-track">
                <div className={`etl-scale-fill risk-${risk}`} />
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
                {cropStage === 'Vegetative' ? 'vegetative' : 'reproductive'} na yugto.
              </p>
            </div>
          </section>
        )}

        <section>
          <h2>NA-DETECT NA RESULTA</h2>
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
