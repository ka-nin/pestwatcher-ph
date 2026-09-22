import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check } from 'lucide-react';
import ScreenHeader from '../components/ScreenHeader';
import { useLanguage } from '../context/LanguageContext';
import './ScanGallery.css';

const TABS = ['All', 'Recent', 'Camera', 'Pest Albums'];

// Placeholder thumbnails standing in for the device photo library.
const PLACEHOLDER_PHOTOS = Array.from({ length: 9 }, (_, i) => ({
  id: i,
  hue: 70 + i * 12,
}));

export default function ScanGallery() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [tab, setTab] = useState('All');
  const [selected, setSelected] = useState(0);

  return (
    <div className="gallery-screen">
      <ScreenHeader title="Select Photo" />

      <div className="gallery-tabs">
        {TABS.map((t) => (
          <button
            key={t}
            className={`gallery-tab${tab === t ? ' active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="gallery-grid">
        {PLACEHOLDER_PHOTOS.map((photo) => (
          <button
            key={photo.id}
            className="gallery-thumb"
            style={{ background: `hsl(${photo.hue}, 35%, 45%)` }}
            onClick={() => setSelected(photo.id)}
          >
            {selected === photo.id && (
              <span className="gallery-thumb-check">
                <Check size={13} />
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="gallery-footer">
        <div className="gallery-footer-row">
          <span>{selected !== null ? '1' : '0'} {t('gallerySelectedSuffix')}</span>
          {selected !== null && (
            <button className="gallery-clear" onClick={() => setSelected(null)}>
              {t('galleryClear')}
            </button>
          )}
        </div>
        <button
          className="gallery-use-btn"
          disabled={selected === null}
          onClick={() => navigate('/scan/analyzing')}
        >
          {t('galleryUseBtn')}
        </button>
      </div>
    </div>
  );
}
