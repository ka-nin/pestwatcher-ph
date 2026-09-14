import { NavLink } from 'react-router-dom';
import { Home, Bell, BookOpen } from 'lucide-react';
import './BottomNav.css';

const tabs = [
  { to: '/home', label: 'Home', icon: Home },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/guide', label: 'Guide', icon: BookOpen },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      <div className="bottom-nav-pill">
        {tabs.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `bottom-nav-item${isActive ? ' active' : ''}`}
          >
            <span className="bottom-nav-icon-wrap">
              <Icon size={20} strokeWidth={2.2} />
            </span>
            <span className="bottom-nav-label">{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
