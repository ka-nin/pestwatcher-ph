import { useEffect, useState } from 'react';
import { Layers } from 'lucide-react';
import './FieldAssessmentCard.css';

// How much damage the photo shows (severity) and how widely it is spread, from
// the field-level damage model (server-python/app/routers/inference.py's
// field_assessment). A 3x3 grid shows which parts of the photo have damage.
// The field size itself is collected upfront on ScanCapture (an INPUT to the
// request, not something to type in after the result) — this card only
// displays affected_hectares as the server already computed it from whatever
// size was submitted (or detected from the photo's own metadata).
// Small areas keep a decimal: rounding 0.5 m² to 1 m² would double it.
const formatM2 = (m2) => (m2 < 10 ? Number(m2.toFixed(1)) : Math.round(m2));

const RISK_CLASS = { Low: 'risk-low', Medium: 'risk-medium', High: 'risk-high' };

function dayLabel(dateStr, isMeasured, t) {
  const d = new Date(dateStr + 'T00:00:00');
  const label = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return isMeasured ? `${label} (${t('scanResultFieldToday')})` : label;
}

function dateRangeLabel(daily) {
  const first = new Date(daily[0].date + 'T00:00:00');
  const last = new Date(daily[daily.length - 1].date + 'T00:00:00');
  const fmt = (d) => d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return `${fmt(first)} – ${fmt(last)}`;
}

function areaText(ha) {
  if (ha == null) return '-';
  // Hectares is the unit the backend already returns; a value under ~0.001 ha
  // (100 m²) reads clearer in square metres than as a near-zero hectare figure.
  return ha < 0.001 ? `${formatM2(ha * 10000)} m²` : `${Number(ha.toFixed(4))} ha`;
}

// Heat-map colour for one grid cell, 0-100 scale (cell values are small
// percentages in practice, so a 15%+ reading already reads as "heavy").
function heatColour(value) {
  if (value <= 0) return 'rgba(0, 0, 0, 0)';
  const strength = Math.min(1, value / 15);
  return `rgba(180, 60, 30, ${0.12 + strength * 0.78})`;
}

function FieldAssessmentCard({ assessment, t, showDisclaimer = true, photo }) {
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  // Same Blob/File-or-URL handling as DetectionOverlay, so the grid can sit
  // directly on top of the actual photo instead of floating on its own —
  // without this, there's no way to tell which real part of the field each
  // cell/percentage refers to.
  const [photoUrl, setPhotoUrl] = useState(typeof photo === 'string' ? photo : null);
  useEffect(() => {
    if (!photo || typeof photo === 'string') {
      setPhotoUrl(photo || null);
      return undefined;
    }
    const made = URL.createObjectURL(photo);
    setPhotoUrl(made);
    return () => URL.revokeObjectURL(made);
  }, [photo]);

  if (!assessment || assessment.status !== 'ok') return null;

  const daily = assessment.daily ?? null;
  const selectedDay = daily?.[selectedDayIndex] ?? null;
  const severityPct = selectedDay?.severity_pct ?? assessment.pct_affected;
  const spreadPct = selectedDay?.spread_pct ?? assessment.cells_affected_pct;
  const affectedHa = selectedDay?.affected_hectares ?? assessment.affected_hectares;
  const hasFieldSize = assessment.field_size_ha != null;

  // The server only scales the photo's AGGREGATE severity per day — it has no
  // per-cell projection. Re-derive the same scale factor already applied to
  // severity_pct and apply it uniformly to every cell, so the grid's existing
  // spatial pattern dims/brightens with the day picker instead of inventing a
  // new spatial prediction. Which cells are "damaged" stays fixed to today's
  // reading — the model never judged which cells will cross the threshold on
  // a future day.
  const cellScale =
    !selectedDay || selectedDay.is_measured || !assessment.pct_affected
      ? 1
      : (selectedDay.severity_pct ?? 0) / assessment.pct_affected;

  // "Stays X for all 14 days" only when the forecast risk never changes —
  // a quick read of the day strip's own risk_level values, nothing new.
  const allSameRisk = daily && daily.length > 0 && daily.every((d) => d.risk_level === daily[0].risk_level);

  return (
    <section className="scan-result-signal field-assessment-card">
      <div className="field-assessment-section">
        <div className="field-assessment-section-head">
          <span className="field-assessment-section-title">{t('scanResultDamageMapTitle')}</span>
          <span className="field-assessment-section-source">{t('scanResultDamageMapSource')}</span>
        </div>
        <div className="field-assessment-map-card">
          <div className={`field-assessment-photo-wrap${photoUrl ? '' : ' no-photo'}`}>
            {photoUrl && <img src={photoUrl} alt={t('scanResultDamageMapTitle')} className="field-assessment-photo" />}
            <div
              className="field-assessment-grid"
              style={{ gridTemplateColumns: `repeat(${assessment.cols}, 1fr)` }}
              aria-label={t('scanResultFieldGridLabel')}
            >
              {assessment.cell_values.flat().map((v, i) => {
                const scaled = v * cellScale;
                return (
                  <div key={i} className="field-assessment-cell" style={{ background: heatColour(scaled) }}>
                    {scaled.toFixed(1)}%
                  </div>
                );
              })}
            </div>
          </div>
          <div className="field-assessment-heat-legend">
            <span>{t('scanResultHeatNone')}</span>
            <span className="field-assessment-heat-bar" />
            <span>{t('scanResultHeatHeavy')}</span>
          </div>
          <p className="field-assessment-note">{t('scanResultDamageMapHint')}</p>
        </div>
      </div>

      <div className="field-assessment-metric-row">
        <div className="field-assessment-metric-card">
          <span className="field-assessment-metric-label">{t('scanResultFieldSeverity')}</span>
          <strong className="field-assessment-metric-value">{severityPct.toFixed(1)}%</strong>
          <span className="field-assessment-metric-hint">{t('scanResultSeverityHint')}</span>
        </div>
        <div className="field-assessment-metric-card">
          <span className="field-assessment-metric-label">{t('scanResultFieldSpread')}</span>
          <strong className="field-assessment-metric-value">{Math.round(spreadPct)}%</strong>
          <span className="field-assessment-metric-hint">{t('scanResultSpreadHint')}</span>
        </div>
      </div>

      <div className="field-assessment-area-card">
        <span className="field-assessment-area-icon">
          <Layers size={18} />
        </span>
        <div className="field-assessment-area-body">
          <span className="field-assessment-area-title">{t('scanResultAffectedAreaTitle')}</span>
          {hasFieldSize ? (
            <span className="field-assessment-area-value">{areaText(affectedHa)}</span>
          ) : (
            <span className="field-assessment-area-prompt">{t('scanResultAffectedAreaAddPrompt')}</span>
          )}
        </div>
      </div>

      {daily && daily.length > 0 && (
        <div className="field-assessment-outlook">
          <div className="field-assessment-outlook-head">
            <span className="field-assessment-outlook-title">{t('scanResultFieldOutlookTitle')}</span>
            <span className="field-assessment-outlook-range">{dateRangeLabel(daily)}</span>
          </div>
          {allSameRisk && (
            <p className="field-assessment-outlook-summary">
              <span className={`field-assessment-risk-pill ${RISK_CLASS[daily[0].risk_level]}`}>{daily[0].risk_level}</span>
              {' '}
              {t('scanResultOutlookStaysSame').replace('{risk}', daily[0].risk_level)}
            </p>
          )}
          <div className="field-assessment-day-strip">
            {daily.map((d, i) => (
              <button
                key={d.date}
                type="button"
                className={`field-assessment-day-btn ${RISK_CLASS[d.risk_level]}${i === selectedDayIndex ? ' is-selected' : ''}`}
                onClick={() => setSelectedDayIndex(i)}
                aria-label={dayLabel(d.date, d.is_measured, t)}
              />
            ))}
          </div>
          <div className="field-assessment-day-range-labels">
            <span>{dayLabel(daily[0].date, daily[0].is_measured, t)}</span>
            <span>{dayLabel(daily[daily.length - 1].date, false, t)}</span>
          </div>
          {selectedDay && (
            <p className="field-assessment-outlook-count">
              {t(selectedDay.is_measured ? 'scanResultOutlookPestCountToday' : 'scanResultOutlookPestCountOn').replace(
                '{date}',
                dayLabel(selectedDay.date, false, t),
              )}
              <strong>{selectedDay.pest_level.toFixed(2)}</strong>
            </p>
          )}
          <p className="field-assessment-note">
            {selectedDay?.is_measured ? t('scanResultFieldMeasuredNote') : t('scanResultFieldProjectedNote')}
          </p>
        </div>
      )}

      {hasFieldSize && (
        <p className="field-assessment-note">
          {t(assessment.field_size_source === 'photo_metadata' ? 'scanResultFieldSizeAuto' : 'scanResultFieldSizeUsed').replace(
            '{ha}',
            assessment.field_size_ha,
          )}
        </p>
      )}
      {showDisclaimer ? <p className="field-assessment-note">{t('scanResultFieldDisclaimer')}</p> : null}
    </section>
  );
}

export default FieldAssessmentCard;
