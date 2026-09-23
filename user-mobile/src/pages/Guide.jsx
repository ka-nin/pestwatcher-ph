import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronRight } from 'lucide-react';
import { pestGuide } from '../data/mockData';
import { PestIcon, getPestIcon } from '../data/pestIcons';
import { useLanguage } from '../context/LanguageContext';
import './Guide.css';

const FILTERS = [
  { id: 'all', labelKey: 'guideFilterAll' },
  { id: 'Rice Pests', labelKey: 'guideFilterPests' },
  { id: 'Diseases', labelKey: 'guideFilterDiseases' },
  { id: 'Prevention', labelKey: 'guideFilterPrevention' },
];

// Same tints the risk badges use — pulled from the shared tokens in
// index.css rather than re-typed here, so a "High Danger" chip and a
// "High Risk" badge can't drift apart visually.
const DANGER_STYLE = {
  'High Danger': { bg: 'var(--risk-high-bg)', color: 'var(--risk-high-fg)' },
  'Warning Limit': { bg: 'var(--risk-medium-bg)', color: 'var(--risk-medium-fg)' },
  'Critical Risk': { bg: 'var(--risk-critical-bg)', color: 'var(--risk-critical-fg)' },
};

export default function Guide() {
  const navigate = useNavigate();
  const { language, t } = useLanguage();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');

  const results = useMemo(() => {
    return pestGuide.filter((entry) => {
      const matchesFilter = filter === 'all' || entry.category === filter;
      const q = query.trim().toLowerCase();
      const matchesQuery =
        !q ||
        entry.name.toLowerCase().includes(q) ||
        entry.nameFil.toLowerCase().includes(q) ||
        entry.scientificName.toLowerCase().includes(q);
      return matchesFilter && matchesQuery;
    });
  }, [query, filter]);

  return (
    <div className="guide-screen">
      <div className="guide-hero hero-surface">
        <span className="guide-eyebrow">{t('guideEyebrow')}</span>
        <h1>{t('guideTitle')}</h1>
        <p>{t('guideSubtitle')}</p>
        <div className="guide-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('guideSearchPlaceholder')}
          />
        </div>
      </div>

      <div className="guide-body">
        <div className="guide-filters">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              className={`guide-filter-chip${filter === f.id ? ' active' : ''}`}
              onClick={() => setFilter(f.id)}
            >
              {t(f.labelKey)}
            </button>
          ))}
        </div>

        <div className="guide-results-count">
          {t('guideResultsTitle')} <span>{results.length} {t('guideResultsCount')}</span>
        </div>

        <div className="guide-list">
          {results.map((entry) => {
            const dangerStyle = DANGER_STYLE[entry.dangerLevel] || DANGER_STYLE['Warning Limit'];
            return (
              <button
                key={entry.id}
                className="guide-card"
                onClick={() => navigate(`/guide/${entry.id}`)}
              >
                <div
                  className="guide-card-thumb"
                  style={{ background: `${getPestIcon(entry.id).tint}1a` }}
                >
                  <PestIcon id={entry.id} size={22} />
                </div>
                <div className="guide-card-body">
                  <div className="guide-card-top">
                    <span className="guide-card-category">
                      {language === 'en' ? entry.category : entry.categoryFil}
                    </span>
                    <span
                      className="guide-card-danger"
                      style={{ background: dangerStyle.bg, color: dangerStyle.color }}
                    >
                      {entry.dangerLevel}
                    </span>
                  </div>
                  <h3>{language === 'en' ? entry.nameEn || entry.name : entry.name}</h3>
                  <p className="guide-card-fil">
                    {language === 'en' ? entry.scientificName || '' : entry.nameFil}
                  </p>
                  <p className="guide-card-summary">
                    {language === 'en' ? entry.summaryEn || entry.summary : entry.summary}
                  </p>
                </div>
                <ChevronRight size={18} color="var(--color-text-muted)" />
              </button>
            );
          })}
          {results.length === 0 && (
            <p className="guide-empty">{t('guideEmpty')}</p>
          )}
        </div>
      </div>
    </div>
  );
}
