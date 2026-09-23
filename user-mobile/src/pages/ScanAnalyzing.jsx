import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wifi } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { useLanguage } from '../context/LanguageContext';
import './ScanAnalyzing.css';

export default function ScanAnalyzing() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  useEffect(() => {
    const timer = setTimeout(() => navigate('/scan/result'), 2600);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="analyzing-screen">
      <ScreenHeader title={t('scanCaptureTitle')} />

      <div className="analyzing-body">
        <div className="analyzing-frame">
          <div className="analyzing-target">
            <span className="analyzing-pulse" />
          </div>
          <div className="analyzing-badge">{t('scanAnalyzingBadge')}</div>
        </div>

        <h2>{t('scanAnalyzingHeading')}</h2>
        <p>{t('scanAnalyzingBody')}</p>

        <div className="analyzing-server-card">
          <Wifi size={18} color="var(--color-primary)" />
          <div>
            <strong>AI Diagnostic Server</strong>
            <span>{t('scanAnalyzingServerStatus')}</span>
          </div>
        </div>

        <button className="analyzing-cancel" onClick={() => navigate('/scan')}>
          {t('scanAnalyzingCancel')}
        </button>
      </div>
    </div>
  );
}
