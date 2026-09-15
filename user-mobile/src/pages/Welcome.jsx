import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Check, LocateFixed } from 'lucide-react';
import riceFieldImg from '../assets/rice-field.png';
import logoImg from '../assets/logo-shield.png';
import { fetchMunicipalities } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { findNearest } from '../utils/geo';
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
      .catch((err) => setError(err.message || 'Hindi ma-connect sa server. Subukan ulit.'))
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
          <div className="welcome-intro-brand">
            <img src={logoImg} alt="" className="welcome-intro-logo" />
            <span>
              PESTWATCHER<sup>PH</sup>
            </span>
          </div>

          <h1 className="welcome-intro-headline">
            <span className="welcome-intro-headline-accent">Ang Bagong Yugto</span>
            <span className="welcome-intro-headline-primary">ng Agrikultura</span>
          </h1>
          <p className="welcome-intro-tagline">
            Pangmatagalang solusyon sa pagsasaka para sa mas magandang bukas
          </p>
        </div>
      </div>
    );
  }

  if (stage === 'setup') {
    return (
      <div className="welcome-screen welcome-screen-setup">
        <div className="welcome-setup-content">
          <h1>Kumpirmahin ang iyong lokasyon</h1>
          <p>Batay sa GPS ng iyong device, ito ang pinakamalapit na sakop na sinusuportahan ng forecast model.</p>

          {error && <p className="welcome-login-error">{error}</p>}

          {loadingList && !municipalities.length ? (
            <p className="welcome-setup-loading">Kinukuha ang iyong lokasyon...</p>
          ) : (
            <>
              <div className="welcome-setup-detected">
                <LocateFixed size={13} />
                {nearestKm != null ? `Awtomatikong natukoy · ~${nearestKm}km ang layo` : 'Awtomatikong natukoy'}
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
              <p className="welcome-setup-override">Hindi tama? Pumili ng ibang munisipyo sa itaas.</p>
            </>
          )}

          <label className="welcome-setup-name">
            <span>Pangalan (opsyonal)</span>
            <input
              type="text"
              placeholder="Juan Dela Cruz"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </label>

          <button className="welcome-cta welcome-cta-dark" onClick={handleContinue} disabled={!selected}>
            Magpatuloy
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="welcome-screen" style={{ backgroundImage: `url(${riceFieldImg})` }}>
      <div className="welcome-content">
        <div className="welcome-brand-block">
          <img src={logoImg} alt="PestWatcher PH" className="welcome-logo-img" />
          <h1>
            PESTWATCHER<sup>PH</sup>
          </h1>
          <p>Pangmatagalang solusyon sa pagsasaka para sa mas magandang bukas</p>
        </div>

        <button className="welcome-cta" onClick={() => setStage('setup')}>
          Simulan
        </button>
      </div>
    </div>
  );
}
