import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronRight } from 'lucide-react';
import { pestGuide } from '../data/mockData';
import { PestIcon, getPestIcon } from '../data/pestIcons';
import { useLanguage } from '../context/LanguageContext';
import { pestNames } from '../utils/pestNames';
import './Guide.css';

const FILTERS = [
  { id: 'all', labelKey: 'guideFilterAll' },
  { id: 'Rice Pests', labelKey: 'guideFilterPests' },
  { id: 'Diseases', labelKey: 'guideFilterDiseases' },
  { id: 'Prevention', labelKey: 'guideFilterPrevention' },
];

// Whether this entry is one of the two pests the app's BiLSTM forecaster
// actively tracks (isTracked: true in mockData.js), vs. general reference
// material (a symptom/disease those pests cause, or a prevention guide).
// Deliberately NOT a Low/Medium/High danger rating — that scale is reserved
// for the live forecast risk shown elsewhere, and reusing it here for a
// static per-entry rating read as if it were that same live number.
const TRACKED_STYLE = { bg: 'var(--risk-high-bg)', color: 'var(--risk-high-fg)' };
const REFERENCE_STYLE = { bg: 'var(--color-border)', color: 'var(--color-text-muted)' };


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
            const trackedStyle = entry.isTracked ? TRACKED_STYLE : REFERENCE_STYLE;
            const names = pestNames(entry, language);
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
                      style={{ background: trackedStyle.bg, color: trackedStyle.color }}
                    >
                      {t(entry.isTracked ? 'guideTrackedBadge' : 'guideReferenceBadge')}
                    </span>
                  </div>
                  <h3>{names.primary}</h3>
                  {names.secondary && <p className="guide-card-fil">{names.secondary}</p>}
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
