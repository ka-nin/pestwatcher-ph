const RISK_STYLES = {
  low: { bg: '#e5f2df', color: 'var(--color-primary-dark)' },
  medium: { bg: '#fbeacd', color: '#8a5a10' },
  high: { bg: '#fbe0de', color: '#a52f28' },
};

export default function RiskBadge({ level, label }) {
  const style = RISK_STYLES[level] || RISK_STYLES.low;
  return (
    <span
      style={{
        display: 'inline-block',
        background: style.bg,
        color: style.color,
        fontSize: 11,
        fontWeight: 700,
        padding: '4px 10px',
        borderRadius: 999,
        letterSpacing: 0.2,
      }}
    >
      {label}
    </span>
  );
}
