import { useState } from 'react';
import './FieldAssessmentCard.css';

// How much damage the photo shows (severity) and how widely it is spread, from
// the field-level damage model (server-python/app/routers/inference.py's
// field_assessment). A 3x3 grid shows which parts of the photo have damage;
// with the farmer's field size, the affected hectares are worked out here.
function FieldAssessmentCard({ assessment, t, showDisclaimer = true }) {
  const [fieldSize, setFieldSize] = useState('');
  if (!assessment || assessment.status !== 'ok') return null;

  // The server reads the size from the photo's drone metadata when it can; a typed value overrides it.
  const detectedSize = assessment.field_size_ha;
  const typed = Number(fieldSize);
  const hasTyped = fieldSize.trim() !== '' && Number.isFinite(typed) && typed > 0;
  const size = hasTyped ? typed : detectedSize;
  const hasSize = Number.isFinite(size) && size > 0;
  const hectares = hasSize ? ((assessment.cells_affected_pct / 100) * size).toFixed(2) : null;

  return (
    <section className="scan-result-signal field-assessment-card">
      <span className="scan-result-signal-label">{t('scanResultFieldTitle')}</span>
      <div className="field-assessment-body">
        <div
          className="field-assessment-grid"
          style={{ gridTemplateColumns: `repeat(${assessment.cols}, 1fr)` }}
          aria-label={t('scanResultFieldGridLabel')}
        >
          {assessment.cell_values.flat().map((v, i) => (
            <div
              key={i}
              className={`field-assessment-cell${assessment.cell_has_damage.flat()[i] ? ' is-damaged' : ''}`}
              style={assessment.cell_has_damage.flat()[i] ? { opacity: Math.min(1, 0.45 + v / 6) } : undefined}
            >
              {v.toFixed(1)}%
            </div>
          ))}
        </div>
        <div className="field-assessment-metrics">
          <div>
            <strong>{assessment.pct_affected.toFixed(1)}%</strong>
            <small>{t('scanResultFieldSeverity')}</small>
          </div>
          <div>
            <strong>{Math.round(assessment.cells_affected_pct)}%</strong>
            <small>{t('scanResultFieldSpread')}</small>
          </div>
          <div>
            <strong>
              {hectares != null
                ? `${hectares} ha`
                : assessment.affected_area_m2 != null
                  ? `~${Math.round(assessment.affected_area_m2)} m²`
                  : '-'}
            </strong>
            <small>{t('scanResultFieldHectares')}</small>
          </div>
        </div>
      </div>
      <label className="field-assessment-size">
        <span>{t('scanResultFieldSize')}</span>
        <input
          type="number"
          inputMode="decimal"
          min="0"
          step="0.1"
          placeholder={detectedSize ? String(detectedSize) : '1.5'}
          value={fieldSize}
          onChange={(e) => setFieldSize(e.target.value)}
        />
      </label>
      {!hasTyped && detectedSize ? <p className="field-assessment-note">{t('scanResultFieldSizeAuto').replace('{ha}', detectedSize)}</p> : null}
      {!hasSize && assessment.affected_area_m2 != null ? (
        <p className="field-assessment-note">
          {t('scanResultFieldAreaFromPhoto')
            .replace('{visible}', Math.round(assessment.visible_area_m2))
            .replace('{low}', Math.round(assessment.affected_area_m2_low))
            .replace('{high}', Math.round(assessment.affected_area_m2_high))}
        </p>
      ) : null}
      {showDisclaimer ? <p className="field-assessment-note">{t('scanResultFieldDisclaimer')}</p> : null}
    </section>
  );
}

export default FieldAssessmentCard;
