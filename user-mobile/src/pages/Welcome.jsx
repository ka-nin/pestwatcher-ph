import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Check, LocateFixed, ChevronDown } from 'lucide-react';
import riceFieldImg from '../assets/rice-field.png';
// Tightly-cropped variant — see Home.jsx's note on logo-shield-mark.png. The
// padded original (logo-shield.png) leaves too much transparent margin once
// a box is sized/spaced tightly around it, as both logo spots in this file
// now are.
import logoMarkImg from '../assets/logo-shield-mark.png';
import { fetchMunicipalities } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { findNearest } from '../utils/geo';
import LanguageToggle from '../components/LanguageToggle';
import './Welcome.css';

// Simulated GPS fix for this demo — a real device's navigator.geolocation
// would report wherever it actually is, which won't be Nueva Ecija on a dev
// machine. Standing this in keeps the nearest-municipality auto-assignment
// below testable without needing a real farmer physically in the province.
// Swap this back to a real navigator.geolocation.getCurrentPosition() call
// once testing off real devices in the field.
const SIMULATED_GPS_FIX = { latitude: 15.58, longitude: 120.95 };

// No farmer accounts exist — there's nothing to sign into. On first launch
// we read the farmer's GPS location and auto-assign whichever municipality
// in /api/locations/municipalities (the handful the BiLSTM model covers)
// is nearest, letting them override it if it's wrong. That choice — plus
// an optional display name for report attribution — is stored on the
// device (see AuthContext) and stands in for a login everywhere else.
export default function Welcome() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const { t } = useLanguage();
  const [stage, setStage] = useState('intro'); // 'intro' -> 'cta' -> 'setup'
  const [municipalities, setMunicipalities] = useState([]);
  const [selected, setSelected] = useState('');
  const [nearestKm, setNearestKm] = useState(null);
  const [fullName, setFullName] = useState('');
  const [loadingList, setLoadingList] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (stage !== 'setup' || municipalities.length) return;
    setLoadingList(true);
    setError('');
    fetchMunicipalities()
      .then((list) => {
        setMunicipalities(list);
        const match = findNearest(SIMULATED_GPS_FIX.latitude, SIMULATED_GPS_FIX.longitude, list, (m) => [
          m.latitude,
          m.longitude,
        ]);
        if (match) {
          setSelected(match.nearest.municipality);
          setNearestKm(Math.round(match.distanceKm));
        } else if (list.length) {
          setSelected(list[0].municipality);
        }
      })
      .catch((err) => setError(err.message || t('welcomeConnectError')))
      .finally(() => setLoadingList(false));
  }, [stage, municipalities.length]);

  const handleContinue = () => {
    const match = municipalities.find((m) => m.municipality === selected);
    if (!match) return;
    setUser({
      fullName: fullName.trim() || null,
      municipality: match.municipality,
      province: match.province,
      latitude: match.latitude,
      longitude: match.longitude,
    });
    navigate('/home');
  };

  if (stage === 'intro') {
    return (
      <div
        className="welcome-screen welcome-screen-intro"
        style={{ backgroundImage: `url(${riceFieldImg})` }}
        onClick={() => setStage('cta')}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setStage('cta')}
      >
        <div className="welcome-intro-content">
          <div className="welcome-intro-badge">
            <img src={logoMarkImg} alt="" className="welcome-intro-logo" />
            <span>
              PESTWATCHER<sup>PH</sup>
            </span>
          </div>

          <div className="welcome-intro-bottom">
            <h1 className="welcome-intro-headline">
              <span className="welcome-intro-headline-accent">{t('welcomeHeadlineAccent')}</span>
              <span className="welcome-intro-headline-primary">{t('welcomeHeadlinePrimary')}</span>
            </h1>
            <p className="welcome-intro-tagline">{t('welcomeTagline')}</p>
          </div>

          <div className="welcome-intro-hint">
            <span>{t('welcomeTapHint')}</span>
            <ChevronDown size={16} />
          </div>
        </div>
      </div>
    );
  }

  if (stage === 'setup') {
    return (
      <div className="welcome-screen welcome-screen-setup">
        <div className="welcome-setup-content">
          <div className="welcome-setup-langrow">
            <LanguageToggle variant="light" />
          </div>
          <h1>{t('welcomeSetupTitle')}</h1>
          <p className="welcome-setup-subtitle">{t('welcomeSetupSubtitle')}</p>

          {error && <p className="welcome-login-error">{error}</p>}

          {loadingList && !municipalities.length ? (
            <p className="welcome-setup-loading">{t('welcomeSetupLoading')}</p>
          ) : (
            <>
              <div className="welcome-setup-detected">
                <LocateFixed size={13} />
                {nearestKm != null
                  ? `${t('welcomeSetupDetected')} · ~${nearestKm}km ${t('welcomeSetupDetectedAway')}`
                  : t('welcomeSetupDetected')}
              </div>
              <div className="municipality-list">
                {municipalities.map((m) => (
                  <button
                    key={m.municipality}
                    type="button"
                    className={`municipality-option${selected === m.municipality ? ' active' : ''}`}
                    onClick={() => setSelected(m.municipality)}
                  >
                    <MapPin size={16} />
                    <span className="municipality-option-text">
                      <strong>{m.municipality}</strong>
                      <small>{m.province}</small>
                    </span>
                    {selected === m.municipality && <Check size={16} />}
                  </button>
                ))}
              </div>
              <p className="welcome-setup-override">{t('welcomeSetupOverride')}</p>
            </>
          )}

          <label className="welcome-setup-name">
            <span>{t('welcomeSetupNameLabel')}</span>
            <input
              type="text"
              placeholder={t('welcomeSetupNamePlaceholder')}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </label>

          <button className="welcome-cta welcome-cta-dark" onClick={handleContinue} disabled={!selected}>
            {t('welcomeContinueBtn')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="welcome-screen welcome-screen-cta" style={{ backgroundImage: `url(${riceFieldImg})` }}>
      <div className="welcome-content">
        <div className="welcome-langrow">
          <LanguageToggle variant="dark" />
        </div>
        <div className="welcome-center">
          <div className="welcome-brand-block">
            <img src={logoMarkImg} alt="PestWatcher PH" className="welcome-logo-img" />
            <h1>
              PESTWATCHER<sup>PH</sup>
            </h1>
            <p>{t('welcomeTagline')}</p>
          </div>
        </div>

        <button className="welcome-cta welcome-cta-hero" onClick={() => setStage('setup')}>
          {t('welcomeCtaStart')}
        </button>
      </div>
    </div>
  );
}
