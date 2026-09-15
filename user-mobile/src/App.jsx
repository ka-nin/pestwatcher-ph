import { HashRouter, Routes, Route, Navigate, useLocation, matchPath } from 'react-router-dom';
import BottomNav from './components/BottomNav';
import AlertsFab from './components/AlertsFab';
import StatusBar from './components/StatusBar';
import Welcome from './pages/Welcome';
import Home from './pages/Home';
import Alerts from './pages/Alerts';
import Guide from './pages/Guide';
import GuideDetail from './pages/GuideDetail';
import ScanCapture from './pages/ScanCapture';
import ScanAnalyzing from './pages/ScanAnalyzing';
import ScanGallery from './pages/ScanGallery';
import ScanResult from './pages/ScanResult';
import ManualReport from './pages/ManualReport';
import MapExpanded from './pages/MapExpanded';
import { useAuth } from './context/AuthContext';

const TABS_WITH_NAV = ['/home', '/alerts', '/guide'];

// Routes whose topmost content is a dark/solid-color hero or header, which
// needs white status bar text. Everything else sits on the app's light
// gradient background and uses dark text (the StatusBar default).
const DARK_STATUS_BAR_PATTERNS = [
  '/home',
  '/alerts',
  '/alerts/map',
  '/guide',
  '/guide/:id',
  '/scan/result',
  '/scan',
  '/scan/analyzing',
  '/scan/gallery',
  '/report',
];

function RequireAuth({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/" replace />;
}

function AppShell() {
  const location = useLocation();
  const { user } = useAuth();
  const showNav = TABS_WITH_NAV.includes(location.pathname) && user;
  const needsDarkStatusBar = DARK_STATUS_BAR_PATTERNS.some((pattern) =>
    matchPath(pattern, location.pathname)
  );

  return (
    <div className="device-frame-wrapper">
      <div className="device-frame">
        <div className={`global-status-bar${needsDarkStatusBar ? ' on-brand' : ''}`}>
          <StatusBar dark={needsDarkStatusBar} />
        </div>
        <div className="app-screen">
          <div className="route-transition" key={location.pathname}>
            <Routes>
              <Route path="/" element={<Welcome />} />
              <Route path="/home" element={<RequireAuth><Home /></RequireAuth>} />
              <Route path="/alerts" element={<RequireAuth><Alerts /></RequireAuth>} />
              <Route path="/guide" element={<RequireAuth><Guide /></RequireAuth>} />
              <Route path="/guide/:id" element={<RequireAuth><GuideDetail /></RequireAuth>} />
              <Route path="/scan" element={<RequireAuth><ScanCapture /></RequireAuth>} />
              <Route path="/scan/analyzing" element={<RequireAuth><ScanAnalyzing /></RequireAuth>} />
              <Route path="/scan/gallery" element={<RequireAuth><ScanGallery /></RequireAuth>} />
              <Route path="/scan/result" element={<RequireAuth><ScanResult /></RequireAuth>} />
              <Route path="/report" element={<RequireAuth><ManualReport /></RequireAuth>} />
              <Route path="/alerts/map" element={<RequireAuth><MapExpanded /></RequireAuth>} />
            </Routes>
          </div>
        </div>
        {location.pathname === '/alerts' && user && <AlertsFab />}
        {showNav && <BottomNav />}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <AppShell />
    </HashRouter>
  );
}
