import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, Edit3, MapPin, Calendar, ChevronDown, Check, X } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { pestTypeOptions, severityOptions, growthStageOptions } from '../data/mockData';
import { submitReport } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import './ManualReport.css';

const todayIso = () => new Date().toISOString().slice(0, 10);

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
  const [error, setError] = useState('');

  const handlePickPhoto = () => fileInputRef.current?.click();

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

  const handleSubmit = async (e) => {
    e.preventDefault();
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

      <form className="report-body" onSubmit={handleSubmit}>
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
          <span>{t('reportFieldEstimatedCount')}</span>
          <div className="report-static-field">
            <input
              type="number"
              min="0"
              step="0.1"
              inputMode="decimal"
              placeholder={t('reportEstimatedPlaceholder')}
              value={estimatedValue}
              onChange={(e) => setEstimatedValue(e.target.value)}
              className="report-date-input"
            />
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

        {error && <p className="report-error">{error}</p>}

        <button className="report-submit" type="submit" disabled={submitted || submitting}>
          {submitted ? t('reportSubmitted') : submitting ? t('reportSubmitting') : t('reportSubmit')}
        </button>
      </form>
    </div>
  );
}
