import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronRight } from 'lucide-react';
import { pestGuide } from '../data/mockData';
import { PestIcon, getPestIcon } from '../data/pestIcons';
import './Guide.css';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'Rice Pests', label: 'Rice Pests' },
  { id: 'Diseases', label: 'Diseases' },
  { id: 'Prevention', label: 'Prevention' },
];

const DANGER_STYLE = {
  'High Danger': { bg: '#fbe0de', color: '#a52f28' },
  'Warning Limit': { bg: '#fbeacd', color: '#8a5a10' },
  'Critical Risk': { bg: '#f6d2ce', color: '#8f1f1a' },
};

export default function Guide() {
  const navigate = useNavigate();
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
      <div className="guide-header">
        <span className="guide-eyebrow">FARMER ENCYCLOPEDIA</span>
        <h1>Pest &amp; Disease Guide</h1>
        <p>Alamin ang tamang solusyon sa peste at sakit sa palay.</p>
        <div className="guide-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Maghanap ng peste o sakit..."
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
              {f.label}
            </button>
          ))}
        </div>

        <div className="guide-results-count">
          Mga Kilalang Peste sa Palayan <span>{results.length} nahanap</span>
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
                    <span className="guide-card-category">{entry.categoryFil}</span>
                    <span
                      className="guide-card-danger"
                      style={{ background: dangerStyle.bg, color: dangerStyle.color }}
                    >
                      {entry.dangerLevel}
                    </span>
                  </div>
                  <h3>{entry.name}</h3>
                  <p className="guide-card-fil">{entry.nameFil}</p>
                  <p className="guide-card-summary">{entry.summary}</p>
                </div>
                <ChevronRight size={18} color="var(--color-text-muted)" />
              </button>
            );
          })}
          {results.length === 0 && (
            <p className="guide-empty">Walang natagpuang resulta.</p>
          )}
        </div>
      </div>
    </div>
  );
}
