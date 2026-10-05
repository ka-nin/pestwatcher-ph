import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, Edit3, MapPin, Calendar, ChevronDown, Check, X, AlertTriangle } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { pestTypeOptions, severityOptions, growthStageOptions } from '../data/mockData';
import { submitReport } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { derivePestCode } from '../utils/pestMatching';
import './ManualReport.css';

const todayIso = () => new Date().toISOString().slice(0, 10);

// Sanity bounds (hectares) for how much affected area a severity level
// plausibly describes. A "High" report covering a sliver of a field, or a
// "Low" one covering several hectares, is probably a mis-tap — the farmer is
// warned, not blocked, since a small but intense infestation can be real.
const HIGH_MIN_AREA_HA = 0.5;
const LOW_MAX_AREA_HA = 2;

function severityMismatch(severity, areaValue) {
  const area = parseFloat(areaValue);
  if (Number.isNaN(area)) return null;
  if (severity === 'high' && area < HIGH_MIN_AREA_HA) return 'highSmall';
  if (severity === 'low' && area >= LOW_MAX_AREA_HA) return 'lowLarge';
  return null;
}

export default function ManualReport() {
  const navigate = useNavigate();
  const { user, growthStage: profileGrowthStage } = useAuth();
  const { language, t } = useLanguage();
  const fileInputRef = useRef(null);
  const pestSelectRef = useRef(null);

  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState(null);

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
  const mismatch = severityMismatch(severity, areaAffected);

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
  const dateLabel = dateSpotted
    ? new Date(`${dateSpotted}T00:00:00`).toLocaleDateString(language === 'en' ? 'en-US' : 'fil-PH', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      })
    : '—';
  const warningEl = mismatch && (
    <div className="report-warning" role="alert">
      <AlertTriangle size={18} />
      <div>
        <strong>{t('reportWarnTitle')}</strong>
        <p>
          {t(mismatch === 'highSmall' ? 'reportWarnHighSmall' : 'reportWarnLowLarge').replace(
            '{area}',
            areaAffected
          )}
        </p>
      </div>
    </div>
  );
  const summaryRows = [
    [t('reportFieldPestType'), pestLabel || '—'],
    [t('reportFieldSeverity'), severityOpt?.[language], severityOpt?.color],
    [t('reportSummaryGrowthStage'), cropGrowthStage],
    [t('reportSummaryArea'), areaAffected !== '' ? `${areaAffected} ${t('reportSummaryHectares')}` : '—'],
    [t('reportSummaryCount'), estimatedValue !== '' ? estimatedValue : '—'],
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
  };

  const handleRemovePhoto = () => {
    setPhotoFile(null);
    setPhotoPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSkipToManual = () => pestSelectRef.current?.focus();

  // Native form validation runs first; only a valid form reaches the
  // confirmation summary, and the report is sent from there.
  const handleReview = (e) => {
    e.preventDefault();
    setError('');
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

      <form className="report-body" onSubmit={handleReview}>
        <label className="report-field">
          <span>{t('reportFieldPestType')}</span>
          <div className="report-select">
            <select ref={pestSelectRef} value={pestType} onChange={(e) => setPestType(e.target.value)} required>
              <option value="" disabled>
                {t('reportPestPlaceholder')}
              </option>
              {pestTypeOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt[language]}
                </option>
              ))}
            </select>
            <ChevronDown size={16} />
          </div>
        </label>

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
        </div>

        <label className="report-field">
          <span>{t('reportFieldGrowthStage')}</span>
          <div className="report-select">
            <select value={cropGrowthStage} onChange={(e) => setCropGrowthStage(e.target.value)} required>
              {growthStageOptions.map((stage) => (
                <option key={stage} value={stage}>
                  {stage}
                </option>
              ))}
            </select>
            <ChevronDown size={16} />
          </div>
        </label>

        {warningEl}

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
        </label>

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

        <label className="report-field">
          <span>{t('reportFieldLocation')}</span>
          <div className="report-static-field">
            <MapPin size={15} color="var(--color-primary)" />
            {user ? `${user.municipality}, ${user.province}` : t('reportNoLocation')}
            <Check size={15} color="var(--color-primary)" style={{ marginLeft: 'auto' }} />
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
