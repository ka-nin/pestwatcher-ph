import { useState } from 'react';
import './FieldAssessmentCard.css';

// How much damage the photo shows (severity) and how widely it is spread, from
// the field-level damage model (server-python/app/routers/inference.py's
// field_assessment). A 3x3 grid shows which parts of the photo have damage;
// with the farmer's field size, the affected hectares are worked out here.
// Small areas keep a decimal: rounding 0.5 m² to 1 m² would double it.
const formatM2 = (m2) => (m2 < 10 ? Number(m2.toFixed(1)) : Math.round(m2));

function FieldAssessmentCard({ assessment, t, showDisclaimer = true }) {
  const [fieldSize, setFieldSize] = useState('');
  const [unit, setUnit] = useState('ha');
  if (!assessment || assessment.status !== 'ok') return null;

  // The server reads the size from the photo's drone metadata when it can; a typed value overrides it.
  const detectedSize = assessment.field_size_ha;
  const typed = Number(fieldSize);
  const hasTyped = fieldSize.trim() !== '' && Number.isFinite(typed) && typed > 0;
  const size = hasTyped ? (unit === 'm2' ? typed / 10000 : typed) : detectedSize; // hectares
  const hasSize = Number.isFinite(size) && size > 0;
  // The damaged share of the photo applied to the field size. A photo has no scale of its own,
  // so there is no area without a size (drone photos supply one).
  const damagedHa = hasSize ? (assessment.pct_affected / 100) * size : null;
  const areaText =
    damagedHa == null ? '-' : unit === 'm2' && hasTyped ? `${formatM2(damagedHa * 10000)} m²` : `${Number(damagedHa.toFixed(4))} ha`;

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
            <strong>{areaText}</strong>
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
          step="any"
          placeholder={unit === 'ha' ? (detectedSize ? String(detectedSize) : '1.5') : '5000'}
          value={fieldSize}
          onChange={(e) => setFieldSize(e.target.value)}
        />
        <select aria-label={t('scanResultFieldSize')} value={unit} onChange={(e) => setUnit(e.target.value)}>
          <option value="ha">{t('scanResultUnitHa')}</option>
          <option value="m2">m²</option>
        </select>
      </label>
      {!hasTyped && detectedSize ? <p className="field-assessment-note">{t('scanResultFieldSizeAuto').replace('{ha}', detectedSize)}</p> : null}
      {!hasSize ? <p className="field-assessment-note">{t('scanResultFieldNeedSize')}</p> : null}
      {showDisclaimer ? <p className="field-assessment-note">{t('scanResultFieldDisclaimer')}</p> : null}
    </section>
  );
}

export default FieldAssessmentCard;
