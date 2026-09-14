import { useNavigate } from 'react-router-dom';
import { Camera } from 'lucide-react';
import './HomeFab.css';

// Rendered as a sibling of the scrolling .app-screen (see App.jsx), not
// nested inside the Home page itself, so it stays visually fixed in the
// device frame while the dashboard content scrolls underneath it. Mirrors
// AlertsFab's structure and styling exactly.
export default function HomeFab() {
  const navigate = useNavigate();
  return (
    <button className="home-fab" onClick={() => navigate('/scan')} aria-label="AI Pest Scan">
      <Camera size={24} />
    </button>
  );
}
