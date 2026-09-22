import './RiskBadge.css';

const LEVELS = ['low', 'medium', 'high'];

export default function RiskBadge({ level, label }) {
  const safeLevel = LEVELS.includes(level) ? level : 'low';
  return <span className={`risk-badge risk-badge-${safeLevel}`}>{label}</span>;
}
