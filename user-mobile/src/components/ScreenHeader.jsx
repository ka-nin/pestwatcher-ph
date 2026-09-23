import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import './ScreenHeader.css';

export default function ScreenHeader({ title, onBack }) {
  const navigate = useNavigate();
  return (
    <header className="screen-header hero-surface">
      <button
        className="screen-header-back"
        onClick={onBack || (() => navigate(-1))}
        aria-label="Go back"
      >
        <ArrowLeft size={20} />
      </button>
      <h1>{title}</h1>
      <span className="screen-header-spacer" />
    </header>
  );
}
