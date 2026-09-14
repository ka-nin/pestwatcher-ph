import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wifi } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import './ScanAnalyzing.css';

export default function ScanAnalyzing() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => navigate('/scan/result'), 2600);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="analyzing-screen">
      <ScreenHeader title="AI Pest Scan" />

      <div className="analyzing-body">
        <div className="analyzing-frame">
          <div className="analyzing-target">
            <span className="analyzing-pulse" />
          </div>
          <div className="analyzing-badge">PAG-ANALYZE NG AI...</div>
        </div>

        <h2>Sinusuri ang peste...</h2>
        <p>
          Ang aming AI ay kasalukuyang kinikilala ang peste sa iyong kinuha na larawan para sa
          tumpak na pag-identify.
        </p>

        <div className="analyzing-server-card">
          <Wifi size={18} color="var(--color-primary)" />
          <div>
            <strong>AI Diagnostic Server</strong>
            <span>May matatag na koneksyon &middot; Tinatayang oras: 5s</span>
          </div>
        </div>

        <button className="analyzing-cancel" onClick={() => navigate('/scan')}>
          Kanselahin ang Pag-scan
        </button>
      </div>
    </div>
  );
}
