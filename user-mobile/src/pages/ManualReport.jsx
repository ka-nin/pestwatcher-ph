import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Calendar, ChevronDown, Check } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { pestTypeOptions, severityOptions } from '../data/mockData';
import { submitReport } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './ManualReport.css';

const todayIso = () => new Date().toISOString().slice(0, 10);

export default function ManualReport() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [pestType, setPestType] = useState('');
  const [severity, setSeverity] = useState('medium');
  const [dateSpotted, setDateSpotted] = useState(todayIso());
  const [notes, setNotes] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await submitReport({
        username: user?.username || 'unknown',
        pest_type: pestType,
        severity,
        province: user?.province || '',
        region: user?.municipality || '',
        date_spotted: dateSpotted,
        notes,
      });
      setSubmitted(true);
      setTimeout(() => navigate('/alerts'), 1400);
    } catch (err) {
      setError(err.message || 'Hindi naisumite ang report. Subukan ulit.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="report-screen">
      <ScreenHeader title="Manual Report" />

      <form className="report-body" onSubmit={handleSubmit}>
        <label className="report-field">
          <span>Pest Type / Uri ng Peste</span>
          <div className="report-select">
            <select value={pestType} onChange={(e) => setPestType(e.target.value)} required>
              <option value="" disabled>
                Pumili ng uri ng peste...
              </option>
              {pestTypeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            <ChevronDown size={16} />
          </div>
        </label>

        <div className="report-field">
          <span>Severity Level</span>
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
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <label className="report-field">
          <span>Location (Account na Naka-login)</span>
          <div className="report-static-field">
            <MapPin size={15} color="var(--color-primary)" />
            {user ? `${user.municipality}, ${user.province}` : 'Walang lokasyon'}
            <Check size={15} color="var(--color-primary)" style={{ marginLeft: 'auto' }} />
          </div>
        </label>

        <label className="report-field">
          <span>Date Spotted</span>
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
          <span>Notes / Karagdagang Detalye</span>
          <textarea
            rows={4}
            placeholder="Ilagay rito ang deskripsyon ng pinsala, tinantyang lawak ng apektadong sakahan, atbp..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>

        {error && <p className="report-error">{error}</p>}

        <button className="report-submit" type="submit" disabled={submitted || submitting}>
          {submitted ? 'Naisumite na!' : submitting ? 'Isinusumite...' : 'I-submit ang Report'}
        </button>
      </form>
    </div>
  );
}
