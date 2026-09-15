import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Lightbulb,
  Thermometer,
  CloudRain,
  Droplets,
  ChevronRight,
  Camera,
  LogOut,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';
import { currentLocation, dashboardSummary } from '../data/mockData';
import { fetchWeatherForecast, fetchPestForecast, fetchPestForecastTrajectory } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useReports } from '../hooks/useReports';
import logoImg from '../assets/logo-shield.png';
import './Home.css';

const LEVEL_COLOR = {
  1: '#7fb356',
  2: '#e0b23c',
  3: '#dd6b3a',
};

const RISK_META = {
  low: { icon: CheckCircle2, accent: '#3f7d3a', accentSoft: 'rgba(63, 125, 58, 0.12)' },
  medium: { icon: AlertTriangle, accent: '#b8791f', accentSoft: 'rgba(184, 121, 31, 0.14)' },
  high: { icon: XCircle, accent: '#b23a2f', accentSoft: 'rgba(178, 58, 47, 0.14)' },
};

const RISK_LABEL_FIL = {
  low: 'Mababang Panganib',
  medium: 'Katamtamang Panganib',
  high: 'Mataas na Panganib',
};

const RISK_MESSAGE_FIL = {
  low: 'Mababa ang posibilidad ng pagtaas ng peste sa loob ng dalawang linggo. Ipagpatuloy ang normal na pagmamanman. Hindi kinakailangan ang agarang pag-ispray ng pestisidyo.',
  medium: 'May pagtaas ng panganib na inaasahan sa loob ng dalawang linggo. Bantayan ang bukid at maghanda ng aksyon.',
  high: 'Mataas ang inaasahang panganib sa loob ng dalawang linggo. Inirerekomenda ang agarang interbensyon.',
};

const PEST_LABEL_FIL = {
  BPH: 'Kayumangging Hanip',
  RSB: 'Aksip o Atip',
};

const RISK_RANK = { Low: 0, Medium: 1, High: 2 };
const WEATHER_REFRESH_MS = 2 * 60 * 1000;

export default function Home() {
  const navigate = useNavigate();
  const { user, growthStage, logout } = useAuth();
  const { reports } = useReports();
  const [weather, setWeather] = useState(null);
  const [weatherUpdatedAt, setWeatherUpdatedAt] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Weather is polled on its own timer so the temp/rainfall/humidity tiles
  // stay live while the app is open, independent of the heavier BiLSTM
  // forecast fetch below (which only needs to re-run when the farmer
  // changes their growth stage).
  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function loadWeather() {
      try {
        const weatherData = await fetchWeatherForecast(user.latitude, user.longitude);
        if (cancelled) return;
        setWeather(weatherData);
        setWeatherUpdatedAt(new Date());
      } catch (err) {
        if (!cancelled) setError(err.message || 'Hindi makuha ang datos ng panahon.');
      }
    }

    loadWeather();
    const intervalId = setInterval(loadWeather, WEATHER_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError('');

    async function loadForecast() {
      try {
        const [bphForecast, rsbForecast, trajectory] = await Promise.all([
          fetchPestForecast(user.municipality, 'BPH', growthStage),
          fetchPestForecast(user.municipality, 'RSB', growthStage),
          fetchPestForecastTrajectory(user.municipality, 'BPH', growthStage, 7),
        ]);
        if (cancelled) return;

        const candidates = [
          { pest: 'BPH', ...bphForecast },
          { pest: 'RSB', ...rsbForecast },
        ].filter((f) => f.status === 'ok');
        const worst = candidates.sort(
          (a, b) => (RISK_RANK[b.risk_level] ?? -1) - (RISK_RANK[a.risk_level] ?? -1)
        )[0];
        setForecast(worst || null);

        if (trajectory.status === 'ok' && trajectory.points.length) {
          setTrend(
            trajectory.points.map((p) => ({
              day: new Date(p.date).toLocaleDateString('en-US', { weekday: 'short' }),
              level: (RISK_RANK[p.risk_level] ?? 0) + 1,
            }))
          );
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Hindi makuha ang datos.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadForecast();
    return () => {
      cancelled = true;
    };
  }, [user, growthStage]);

  const riskLevel = forecast?.risk_level?.toLowerCase() || 'low';
  const risk = RISK_META[riskLevel] || RISK_META.low;
  const RiskIcon = risk.icon;
  const now = new Date();
  const dateTimeLabel = `${now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${now.toLocaleTimeString(
    'en-US',
    { hour: '2-digit', minute: '2-digit', hour12: true }
  )}`;
  const trendData = trend || dashboardSummary.trend;

  const highRiskReports = reports.filter((r) => r.risk === 'high' || r.risk === 'medium');
  const nearbyZones = [...new Set(highRiskReports.map((r) => r.location))];
  const nearbyMaxKm = Math.max(...highRiskReports.map((r) => r.distanceKm).filter((n) => Number.isFinite(n)), 0);

  return (
    <div className="home-screen">
      <div className="home-hero">
        <div className="home-topbar">
          <span className="home-brand">
            <img src={logoImg} alt="" className="home-brand-logo" /> PESTWATCHER<sup>PH</sup>
          </span>
          <span className="home-topbar-right">
            <span className="home-datetime">{dateTimeLabel}</span>
            <button className="home-logout" onClick={() => { logout(); navigate('/'); }} aria-label="Logout">
              <LogOut size={12} />
            </button>
          </span>
        </div>

        <div className="home-location">
          <h1>{user?.province || currentLocation.province}</h1>
          <p>Based on the data gathered from {user?.municipality || currentLocation.region}</p>
        </div>
      </div>

      <div className="home-body">
        {error && <p className="home-error">{error}</p>}

        <section className="hero-risk-card">
          <div className="hero-risk-top">
            <div className="hero-risk-icon" style={{ borderColor: risk.accent, color: risk.accent }}>
              <RiskIcon size={22} strokeWidth={2} />
            </div>
            <span className="hero-risk-chip" style={{ background: risk.accentSoft, color: risk.accent }}>
              {loading ? 'Kinakalkula...' : RISK_LABEL_FIL[riskLevel]}
            </span>
          </div>
          <h2>{forecast ? PEST_LABEL_FIL[forecast.pest] : dashboardSummary.pestFil}</h2>
          <p>
            {loading
              ? 'Kinukuha ang pinakabagong forecast mula sa BiLSTM na modelo...'
              : forecast
                ? RISK_MESSAGE_FIL[riskLevel]
                : 'Hindi pa available ang modelo para sa lugar na ito.'}
          </p>

          <div className="hero-risk-divider" />

          <div className="hero-risk-tip">
            <Lightbulb size={16} color="var(--color-accent-orange)" />
            <p>
              <strong>Payo sa Magsasaka:</strong> {dashboardSummary.tip}
            </p>
          </div>
        </section>

        <section className="weather-tiles-block">
          <div className="weather-tiles-live">
            <span className="weather-tiles-live-dot" />
            Live {weatherUpdatedAt ? `· updated ${weatherUpdatedAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}` : ''}
          </div>
          <div className="weather-tiles">
            <div className="weather-tile">
              <div className="weather-tile-top">
                <span>TEMP</span>
                <Thermometer size={16} color="var(--color-accent-red)" />
              </div>
              <strong>{weather ? Math.round(weather.current.temperature_2m) : '--'}°C</strong>
              <span className="weather-tile-caption">
                {weather ? `Feels ${Math.round(weather.current.apparent_temperature ?? weather.current.temperature_2m)}°C` : '--'}
              </span>
            </div>
            <div className="weather-tile">
              <div className="weather-tile-top">
                <span>RAINFALL</span>
                <CloudRain size={16} color="#5b7fbf" />
              </div>
              <strong>{weather ? weather.current.precipitation : '--'} mm</strong>
              <span className="weather-tile-caption">Now</span>
            </div>
            <div className="weather-tile">
              <div className="weather-tile-top">
                <span>HUMIDITY</span>
                <Droplets size={16} color="var(--color-primary)" />
              </div>
              <strong>{weather ? Math.round(weather.current.relative_humidity_2m) : '--'}%</strong>
              <span className="weather-tile-caption">
                {weather && weather.current.relative_humidity_2m >= 80 ? 'Very High' : 'Normal'}
              </span>
            </div>
          </div>
        </section>

        <section className="trend-card">
          <div className="trend-header">
            <h3>Spore &amp; Pest Level Trend</h3>
            <div className="trend-legend">
              <span><i style={{ background: LEVEL_COLOR[1] }} /> Ligtas</span>
              <span><i style={{ background: LEVEL_COLOR[2] }} /> Babala</span>
              <span><i style={{ background: LEVEL_COLOR[3] }} /> Panganib</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={110}>
            <BarChart data={trendData} barCategoryGap="34%" margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <XAxis
                dataKey="day"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              />
              <YAxis hide domain={[0, 3]} />
              <Bar dataKey="level" radius={[7, 7, 2, 2]} minPointSize={6}>
                {trendData.map((entry, i) => (
                  <Cell key={i} fill={LEVEL_COLOR[entry.level]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>

        {nearbyZones.length > 0 && (
          <button className="nearby-zones-strip" onClick={() => navigate('/alerts')}>
            <AlertTriangle size={18} color="var(--color-accent-orange)" />
            <span className="nearby-zones-text">
              <strong>{nearbyZones.length} High Risk Zones Nearby</strong>
              <small>
                {nearbyZones.join(' & ')} · within {nearbyMaxKm}km
              </small>
            </span>
            <ChevronRight size={16} color="var(--color-text-muted)" />
          </button>
        )}

        <button className="scan-strip" onClick={() => navigate('/scan')}>
          <span className="scan-strip-icon">
            <Camera size={18} />
          </span>
          <span className="scan-strip-text">
            <strong>AI Pest Scan</strong>
            <small>Magsuri ng peste gamit ang iyong camera</small>
          </span>
          <ChevronRight size={16} color="var(--color-text-muted)" />
        </button>

        <div className="report-manual-block">
          <button className="report-manual-cta" onClick={() => navigate('/report')}>
            Report Sighting Manually
          </button>
          <p>No photo? Report what you see · 30 seconds</p>
        </div>
      </div>
    </div>
  );
}
