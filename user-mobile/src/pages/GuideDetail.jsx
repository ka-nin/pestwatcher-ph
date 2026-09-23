import { useParams, useNavigate } from 'react-router-dom';
import { X, ShieldAlert } from 'lucide-react';
import { pestGuide } from '../data/mockData';
import { PestHeroMedia } from '../data/pestIcons';
import { useLanguage } from '../context/LanguageContext';
import './GuideDetail.css';

const DANGER_STYLE = {
  'High Danger': { bg: '#fbe0de', color: '#a52f28' },
  'Warning Limit': { bg: '#fbeacd', color: '#8a5a10' },
  'Critical Risk': { bg: '#f6d2ce', color: '#8f1f1a' },
};

export default function GuideDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { language, t } = useLanguage();
  const entry = pestGuide.find((p) => p.id === id) || pestGuide[0];
  const dangerStyle = DANGER_STYLE[entry.dangerLevel] || DANGER_STYLE['Warning Limit'];
  const isEn = language === 'en';

  const displayName = isEn ? entry.nameEn || entry.name : entry.name;
  const description = isEn ? entry.descriptionEn || entry.description : entry.description;
  const signs = isEn ? entry.signsEn || entry.signs : entry.signs;
  const prevention = isEn ? entry.preventionEn || entry.prevention : entry.prevention;

  return (
    <div className="guide-detail-screen">
      <div className="guide-detail-hero">
        <PestHeroMedia id={entry.id} />
        <div className="guide-detail-hero-scrim" />
        <button className="guide-detail-close" onClick={() => navigate(-1)} aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="guide-detail-sheet">
        <div className="guide-detail-top">
          <span className="guide-detail-category">{isEn ? entry.category : entry.categoryFil}</span>
          <span
            className="guide-detail-danger"
            style={{ background: dangerStyle.bg, color: dangerStyle.color }}
          >
            {entry.dangerLevel}
          </span>
        </div>
        <h1>{displayName}</h1>
        <p className="guide-detail-fil">
          {isEn ? entry.scientificName && <em>{entry.scientificName}</em> : (
            <>
              {entry.nameFil} {entry.scientificName && <em>({entry.scientificName})</em>}
            </>
          )}
        </p>

        <section>
          <h2>{t('guideDetailDescription')}</h2>
          <p>{description}</p>
        </section>

        {signs.length > 0 && (
          <section>
            <h2>{t('guideDetailSigns')}</h2>
            <ul>
              {signs.map((sign) => (
                <li key={sign}>{sign}</li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h2>{entry.category === 'Prevention' ? t('guideDetailHowToApply') : t('guideDetailPrevention')}</h2>
          <ul>
            {prevention.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <div className="guide-detail-footer">
        <button className="guide-detail-report" onClick={() => navigate('/report')}>
          <ShieldAlert size={16} /> {t('guideDetailReportCta')}
        </button>
      </div>
    </div>
  );
}
