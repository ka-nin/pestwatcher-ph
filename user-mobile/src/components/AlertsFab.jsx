import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import './AlertsFab.css';

// Rendered as a sibling of the scrolling .app-screen (see App.jsx), not
// nested inside the Alerts page itself, so it stays visually fixed in the
// device frame while the alerts list and map scroll underneath it.
export default function AlertsFab() {
  const navigate = useNavigate();
  return (
    <button className="alerts-fab" onClick={() => navigate('/report')} aria-label="Report a sighting">
      <Plus size={24} />
    </button>
  );
}
