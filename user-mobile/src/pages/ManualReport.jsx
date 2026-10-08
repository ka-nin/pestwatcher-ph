import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, Edit3, MapPin, Calendar, Lock, X, AlertTriangle } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { pestTypeOptions, severityOptions, growthStageOptions, growthStageLabels, growthStageDescriptions, etlThresholds } from '../data/mockData';
import Dropdown from '../components/Dropdown';
import { submitImageInference, submitReport } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { derivePestCode } from '../utils/pestMatching';

// ResNet-50's BPH/RSB code -> this form's actual pest_type dropdown value.
const PEST_TYPE_BY_CODE = {
  BPH: 'Brown Planthopper (Kayumangging Hanip)',
  RSB: 'Rice Stem Borer (Aksip o Atip)',
};
import './ManualReport.css';

const todayIso = () => new Date().toISOString().slice(0, 10);

// Same Vegetative/Reproductive split as GROWTH_STAGE_BUCKETS in
// server-python/ml/config.py.
const GROWTH_BUCKET = {
  Seedling: 'Vegetative',
  Tillering: 'Vegetative',
  Elongation: 'Vegetative',
  Panicle: 'Reproductive',
  Flowering: 'Reproductive',
  Ripening: 'Reproductive',
};
const GUIDE_ID_BY_PEST = { BPH: 'bph', RSB: 'stem-borer' };

// ETL band (etlThresholds in mockData.js — the thesis ETL table) for this
// pest at this growth stage, plus the unit the number is measured in.
function etlBandFor(pestCode, growthStage) {
  const pest = etlThresholds[GUIDE_ID_BY_PEST[pestCode]];
  const band = pest?.[GROWTH_BUCKET[growthStage] || 'Vegetative'];
  if (!band) return null;
  return { low: band.low, medium: band.medium, unit: band.unit ?? pest.unit };
}

// Table boundaries: below `low` is Low, `low` to `medium` is Medium, above
// `medium` is High.
function riskForValue(value, band) {
  if (value < band.low) return 'low';
  if (value > band.medium) return 'high';
  return 'medium';
}

// "<10", "10–20", ">20" — the range each risk level covers.
function rangeFor(level, band) {
  if (level === 'low') return `<${band.low}`;
  if (level === 'medium') return `${band.low}–${band.medium}`;
  return `>${band.medium}`;
}

// Risk level the affected area (hectares) points to:
//   Low < 0.5 · Medium 0.5 to 1 · High > 1
const AREA_MEDIUM_MIN_HA = 0.5;
const AREA_HIGH_ABOVE_HA = 1;

function riskForArea(area) {
  if (area < AREA_MEDIUM_MIN_HA) return 'low';
  if (area > AREA_HIGH_ABOVE_HA) return 'high';
  return 'medium';
}

const AREA_RANGE = {
  low: `<${AREA_MEDIUM_MIN_HA}`,
  medium: `${AREA_MEDIUM_MIN_HA}–${AREA_HIGH_ABOVE_HA}`,
  high: `>${AREA_HIGH_ABOVE_HA}`,
};

export default function ManualReport() {
  const navigate = useNavigate();
  const { user, growthStage: profileGrowthStage } = useAuth();
  const { language, t } = useLanguage();
  const fileInputRef = useRef(null);
  const pestSelectRef = useRef(null);

  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState(null);
  const [classifying, setClassifying] = useState(false);
  const [classifyResult, setClassifyResult] = useState(null); // { label, confidence } | 'none' | 'error' | null

  const [pestType, setPestType] = useState('');
  const [severity, setSeverity] = useState('medium');
  const [cropGrowthStage, setCropGrowthStage] = useState(profileGrowthStage || 'Tillering');
  const [areaAffected, setAreaAffected] = useState('');
  const [estimatedValue, setEstimatedValue] = useState('');
  const [dateSpotted, setDateSpotted] = useState(todayIso());
  const [notes, setNotes] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');

  const pestLabel = pestTypeOptions.find((o) => o.value === pestType)?.[language];
  const severityOpt = severityOptions.find((o) => o.id === severity);
  // Matches server-python's derive_pest_code() so the unit shown below
  // (hoppers/hill vs %) always agrees with how the backend interprets this
  // same number.
  const pestCode = derivePestCode(pestType);
  const estimatedCountLabelKey =
    pestCode === 'BPH'
      ? 'reportFieldEstimatedCountBph'
      : pestCode === 'RSB'
        ? 'reportFieldEstimatedCountRsb'
        : 'reportFieldEstimatedCount';
  const estimatedUnit =
    pestCode === 'BPH' ? t('reportEstimatedUnitBph') : pestCode === 'RSB' ? t('reportEstimatedUnitRsb') : null;
  const etlBand = pestCode ? etlBandFor(pestCode, cropGrowthStage) : null;
  const estimated = parseFloat(estimatedValue);
  const impliedRisk = etlBand && !Number.isNaN(estimated) ? riskForValue(estimated, etlBand) : null;
  const mismatch = impliedRisk && impliedRisk !== severity ? impliedRisk : null;
  const impliedOpt = severityOptions.find((o) => o.id === mismatch);
  const dateLabel = dateSpotted
    ? new Date(`${dateSpotted}T00:00:00`).toLocaleDateString(language === 'en' ? 'en-US' : 'fil-PH', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      })
    : '—';
  const area = parseFloat(areaAffected);
  const impliedAreaRisk = Number.isNaN(area) ? null : riskForArea(area);
  const areaMismatch = impliedAreaRisk && impliedAreaRisk !== severity ? impliedAreaRisk : null;
  const impliedAreaOpt = severityOptions.find((o) => o.id === areaMismatch);

  const warningBox = (text) => (
    <div className="report-warning" role="alert">
      <AlertTriangle size={18} />
      <div>
        <strong>{t('reportWarnTitle')}</strong>
        <p>{text}</p>
      </div>
    </div>
  );
  const areaWarningEl =
    areaMismatch &&
    warningBox(
      t('reportWarnAreaMismatch')
        .replace('{area}', areaAffected)
        .replace('{implied}', impliedAreaOpt?.[language] ?? '')
        .replace('{range}', `${AREA_RANGE[areaMismatch]} ${t('reportSummaryHectares')}`)
        .replace('{selected}', severityOpt?.[language] ?? '')
    );
  const warningEl =
    mismatch &&
    warningBox(
      t('reportWarnMismatch')
        .replace('{pest}', pestCode)
        .replace('{stage}', growthStageLabels[cropGrowthStage]?.[language] ?? cropGrowthStage)
        .replace('{value}', estimatedValue)
        .replace('{unit}', etlBand.unit)
        .replace('{implied}', impliedOpt?.[language] ?? '')
        .replace('{range}', `${rangeFor(mismatch, etlBand)} ${etlBand.unit}`)
        .replace('{selected}', severityOpt?.[language] ?? '')
    );
  const summaryRows = [
    [t('reportFieldPestType'), pestLabel || '—'],
    [t('reportFieldSeverity'), severityOpt?.[language], severityOpt?.color],
    [t('reportSummaryGrowthStage'), growthStageLabels[cropGrowthStage]?.[language] ?? cropGrowthStage],
    [t('reportSummaryArea'), areaAffected !== '' ? `${areaAffected} ${t('reportSummaryHectares')}` : '—'],
    [t('reportSummaryCount'), estimatedValue !== '' ? `${estimatedValue}${estimatedUnit ? ` ${estimatedUnit}` : ''}` : '—'],
    [t('reportSummaryLocation'), user ? `${user.municipality}, ${user.province}` : t('reportNoLocation')],
    [t('reportFieldDateSpotted'), dateLabel],
    [t('reportSummaryPhoto'), photoFile ? t('reportSummaryPhotoYes') : t('reportSummaryPhotoNo')],
  ];

  const handlePickPhoto =() => fileInputRef.current?.click();

  const handlePhotoChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoFile(file);
    setPhotoPreviewUrl(URL.createObjectURL(file));
    setClassifyResult(null);
    setClassifying(true);

    // Best-effort auto-fill only — the farmer can still change the dropdown
    // below, and submission still runs its own server-side classification
    // (app/routers/reports.py) independent of this. No municipality/growth
    // stage passed: we only want the pest label here, not a forecast.
    submitImageInference(file)
      .then((result) => {
        if (result.status === 'ok' && PEST_TYPE_BY_CODE[result.pest_detected]) {
          setPestType(PEST_TYPE_BY_CODE[result.pest_detected]);
          setClassifyResult({ label: result.pest_detected, confidence: result.confidence });
        } else {
          setClassifyResult('none');
        }
      })
      .catch(() => setClassifyResult('error'))
      .finally(() => setClassifying(false));
  };

  const handleRemovePhoto = () => {
    setPhotoFile(null);
    setPhotoPreviewUrl(null);
    setClassifying(false);
    setClassifyResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSkipToManual = () => pestSelectRef.current?.focus();

  // The pest-type dropdown is a custom component, not a native <select>, so
  // its "required"-ness is no longer enforced by the browser's own form
  // validation — checked explicitly here instead before reaching the
  // confirmation summary.
  const handleReview = (e) => {
    e.preventDefault();
    setError('');
    if (!pestType) {
      pestSelectRef.current?.focus();
      return;
    }
    setShowConfirm(true);
  };

  const handleConfirm = async () => {
    setError('');
    setSubmitting(true);
    try {
      await submitReport(
        {
          username: user?.fullName || 'Anonymous Farmer',
          pest_type: pestType,
          severity,
          crop_growth_stage: cropGrowthStage,
          area_affected: areaAffected,
          estimated_value: estimatedValue,
          province: user?.province || '',
          municipality: user?.municipality || '',
          date_spotted: dateSpotted,
          notes,
          latitude: user?.latitude ?? '',
          longitude: user?.longitude ?? '',
        },
        photoFile
      );
      setSubmitted(true);
      setTimeout(() => navigate('/alerts'), 1400);
      setShowConfirm(false);
    } catch (err) {
      setError(err.message || t('reportSubmitError'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="report-screen">
      <ScreenHeader title={t('reportTitle')} />

      <div className="report-mode-row">
        <button type="button" className="report-mode-photo" onClick={handlePickPhoto}>
          <Camera size={20} />
          <span>{t('reportModePhoto')}</span>
        </button>
        <button type="button" className="report-mode-manual" onClick={handleSkipToManual}>
          <Edit3 size={13} />
          {t('reportModeManual')}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={handlePhotoChange}
        />
      </div>

      {photoPreviewUrl && (
        <div className="report-photo-preview">
          <img src={photoPreviewUrl} alt={t('reportPhotoAlt')} />
          <button type="button" className="report-photo-remove" onClick={handleRemovePhoto} aria-label={t('reportPhotoRemoveAria')}>
            <X size={14} />
          </button>
        </div>
      )}

      {classifying && <p className="report-classify-note">{t('reportClassifying')}</p>}
      {!classifying && classifyResult && classifyResult !== 'none' && classifyResult !== 'error' && (
        <p className="report-classify-note report-classify-note-ok">
          {t('reportClassifiedAs')} {pestTypeOptions.find((o) => derivePestCode(o.value) === classifyResult.label)?.[language]} ({Math.round(classifyResult.confidence * 100)}%) — {t('reportClassifiedEditable')}
        </p>
      )}
      {!classifying && classifyResult === 'none' && (
        <p className="report-classify-note">{t('reportClassifyNone')}</p>
      )}

      <form className="report-body" onSubmit={handleReview}>
        <section className="report-section">
          <h2 className="report-section-title">{t('reportSectionPest')}</h2>

          <div className="report-field">
            <span>{t('reportFieldPestType')}</span>
            <Dropdown
              ref={pestSelectRef}
              value={pestType}
              onChange={setPestType}
              placeholder={t('reportPestPlaceholder')}
              ariaLabel={t('reportFieldPestType')}
              options={pestTypeOptions.map((opt) => ({ value: opt.value, label: opt[language] }))}
            />
          </div>

          <div className="report-field">
            <span>{t('reportFieldSeverity')}</span>
            <div className="severity-options">
              {severityOptions.map((opt) => (
                <button
                  type="button"
                  key={opt.id}
                  className={`severity-pill${severity === opt.id ? ' active' : ''}`}
                  style={severity === opt.id ? { borderColor: opt.color, color: opt.color } : undefined}
                  onClick={() => setSeverity(opt.id)}
                >
                  <span className="severity-dot" style={{ background: opt.color }} />
                  {opt[language]}
                </button>
              ))}
            </div>
            {etlBand && (
              <p className="report-threshold-hint">
                {severityOptions.map((opt, i) => (
                  <span key={opt.id}>
                    {i > 0 && ' · '}
                    <strong>{opt[language]}</strong> {rangeFor(opt.id, etlBand)}
                  </span>
                ))}{' '}
                {etlBand.unit}
              </p>
            )}
          </div>
        </section>

        <section className="report-section">
          <h2 className="report-section-title">{t('reportSectionField')}</h2>

          <div className="report-field">
            <span>{t('reportFieldGrowthStage')}</span>
            <Dropdown
              value={cropGrowthStage}
              onChange={setCropGrowthStage}
              ariaLabel={t('reportFieldGrowthStage')}
              options={growthStageOptions.map((stage) => ({
                value: stage,
                label: growthStageLabels[stage]?.[language] ?? stage,
              }))}
            />
            <p className="report-stage-description">{growthStageDescriptions[cropGrowthStage]?.[language]}</p>
          </div>

          {areaWarningEl}

          <label className="report-field">
            <span>{t('reportFieldAreaAffected')}</span>
            <div className="report-static-field">
              <input
                type="number"
                min="0"
                step="0.1"
                inputMode="decimal"
                placeholder={t('reportAreaPlaceholder')}
                value={areaAffected}
                onChange={(e) => setAreaAffected(e.target.value)}
                className="report-date-input"
              />
            </div>
            <p className="report-threshold-hint">
              {severityOptions.map((opt, i) => (
                <span key={opt.id}>
                  {i > 0 && ' · '}
                  <strong>{opt[language]}</strong> {AREA_RANGE[opt.id]}
                </span>
              ))}{' '}
              {t('reportSummaryHectares')}
            </p>
          </label>

          {warningEl}

          <label className="report-field">
            <span>{t(estimatedCountLabelKey)}</span>
            <div className={`report-static-field${pestCode ? '' : ' report-static-field-disabled'}`}>
              <input
                type="number"
                min="0"
                max={pestCode === 'RSB' ? 100 : undefined}
                step="0.1"
                inputMode="decimal"
                disabled={!pestCode}
                placeholder={pestCode ? t('reportEstimatedPlaceholder') : t('reportEstimatedChoosePestFirst')}
                value={estimatedValue}
                onChange={(e) => setEstimatedValue(e.target.value)}
                className="report-date-input"
              />
              {estimatedUnit && <span className="report-field-unit">{estimatedUnit}</span>}
            </div>
          </label>
        </section>

        <section className="report-section">
          <h2 className="report-section-title">{t('reportSectionDetails')}</h2>

          <label className="report-field">
            <span>{t('reportFieldLocation')}</span>
            <div className="report-static-field report-static-field-readonly" aria-readonly="true">
              <MapPin size={15} />
              {user ? `${user.municipality}, ${user.province}` : t('reportNoLocation')}
              <Lock size={14} style={{ marginLeft: 'auto' }} />
            </div>
          </label>

          <label className="report-field">
            <span>{t('reportFieldDateSpotted')}</span>
            <div className="report-static-field">
              <input
                type="date"
                value={dateSpotted}
                onChange={(e) => setDateSpotted(e.target.value)}
                className="report-date-input"
              />
              <Calendar size={15} color="var(--color-text-muted)" />
            </div>
          </label>

          <label className="report-field">
            <span>{t('reportFieldNotes')}</span>
            <textarea
              rows={4}
              placeholder={t('reportNotesPlaceholder')}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>
        </section>

        <button className="report-submit" type="submit" disabled={submitted || submitting}>
          {submitted ? t('reportSubmitted') : t('reportReview')}
        </button>
      </form>

      {showConfirm && (
        <div
          className="report-modal-backdrop"
          onClick={() => !submitting && !submitted && setShowConfirm(false)}
        >
          <div
            className="report-modal"
            role="dialog"
            aria-modal="true"
            aria-label={t('reportSummaryTitle')}
            onClick={(e) => e.stopPropagation()}
          >
            <h2>{t('reportSummaryTitle')}</h2>
            <p className="report-modal-hint">{t('reportConfirmHint')}</p>

            {areaWarningEl}
            {warningEl}

            <dl>
              {summaryRows.map(([label, value, color]) => (
                <div key={label} className="report-summary-row">
                  <dt>{label}</dt>
                  <dd style={color ? { color, fontWeight: 700 } : undefined}>{value}</dd>
                </div>
              ))}
            </dl>
            {notes.trim() && <p className="report-summary-notes">“{notes.trim()}”</p>}

            {error && <p className="report-error">{error}</p>}

            <div className="report-modal-actions">
              <button
                type="button"
                className="report-modal-edit"
                onClick={() => setShowConfirm(false)}
                disabled={submitting || submitted}
              >
                {t('reportConfirmEdit')}
              </button>
              <button
                type="button"
                className="report-submit report-modal-send"
                onClick={handleConfirm}
                disabled={submitting || submitted}
              >
                {submitted ? t('reportSubmitted') : submitting ? t('reportSubmitting') : t('reportSubmit')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
