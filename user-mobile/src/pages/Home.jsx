import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Lightbulb,
  Thermometer,
  CloudRain,
  Droplets,
  ChevronRight,
  ChevronDown,
  LogOut,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';
import { currentLocation, dashboardSummary } from '../data/mockData';
import { fetchWeatherForecast, fetchPestForecast, fetchPestForecastTrajectory } from '../api/client';
import { useAuth } from '../context/AuthContext';
import logoImg from '../assets/logo.png';
import './Home.css';

const LEVEL_COLOR = {
  1: '#7fb356',
  2: '#e0b23c',
  3: '#dd6b3a',
};

const RISK_META = {
  low: {
    icon: ShieldCheck,
    accent: '#3f7d3a',
    accentSoft: 'rgba(63, 125, 58, 0.12)',
    gradient:
      'radial-gradient(120% 140% at 100% 0%, #6ba362 0%, #3f7d3a 32%, #2f5f2c 68%, #1f4020 100%)',
  },
  medium: {
    icon: ShieldAlert,
    accent: '#b8791f',
    accentSoft: 'rgba(184, 121, 31, 0.14)',
    gradient:
      'radial-gradient(120% 140% at 100% 0%, #ddc066 0%, #c9a227 32%, #9a7a1c 68%, #6b5312 100%)',
  },
  high: {
    icon: ShieldX,
    accent: '#b23a2f',
    accentSoft: 'rgba(178, 58, 47, 0.14)',
    gradient:
      'radial-gradient(120% 140% at 100% 0%, #e37c6e 0%, #d64545 32%, #a3312f 68%, #6e211f 100%)',
  },
};

const RISK_MESSAGE_FIL = {
  low: 'Mababa ang posibilidad ng pagtaas ng peste sa loob ng dalawang linggo. Ipagpatuloy ang normal na pagmamanman.',
  medium: 'May pagtaas ng panganib na inaasahan sa loob ng dalawang linggo. Bantayan ang bukid at maghanda ng aksyon.',
  high: 'Mataas ang inaasahang panganib sa loob ng dalawang linggo. Inirerekomenda ang agarang interbensyon.',
};

const GROWTH_STAGES = ['Seedling', 'Tillering', 'Elongation', 'Panicle', 'Flowering', 'Ripening'];

const PEST_LABEL_FIL = {
  BPH: 'Kayumangging Hanip',
  RSB: 'Aksip o Atip',
};

const RISK_RANK = { Low: 0, Medium: 1, High: 2 };

export default function Home() {
  const navigate = useNavigate();
  const { user, growthStage, setGrowthStage, logout } = useAuth();
  const [weather, setWeather] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError('');

    async function loadDashboard() {
      try {
        const [weatherData, bphForecast, rsbForecast, trajectory] = await Promise.all([
          fetchWeatherForecast(user.latitude, user.longitude),
          fetchPestForecast(user.municipality, 'BPH', growthStage),
          fetchPestForecast(user.municipality, 'RSB', growthStage),
          fetchPestForecastTrajectory(user.municipality, 'BPH', growthStage, 7),
        ]);
        if (cancelled) return;

        setWeather(weatherData);

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

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [user, growthStage]);

  const riskLevel = forecast?.risk_level?.toLowerCase() || 'low';
  const risk = RISK_META[riskLevel] || RISK_META.low;
  const RiskIcon = risk.icon;
  const today = new Date();
  const dateLabel = today.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const trendData = trend || dashboardSummary.trend;

  return (
    <div className="home-screen">
      <div className="home-topbar">
        <span className="home-brand">
          <img src={logoImg} alt="" className="home-brand-logo" /> PESTWATCHER<sup>PH</sup>
        </span>
        <span className="home-topbar-right">
          <span className="home-datetime">{dateLabel}</span>
          <button className="home-logout" onClick={() => { logout(); navigate('/'); }} aria-label="Logout">
            <LogOut size={13} />
          </button>
        </span>
      </div>

      <div className="home-location">
        <h1>{user?.municipality || currentLocation.province}</h1>
        <p>{user?.province || currentLocation.region}</p>
      </div>

      <div className="home-body">
        <label className="growth-stage-select">
          <span>Yugto ng Paglaki / Growth Stage</span>
          <div className="growth-stage-select-control">
            <select value={growthStage} onChange={(e) => setGrowthStage(e.target.value)}>
              {GROWTH_STAGES.map((stage) => (
                <option key={stage} value={stage}>
                  {stage}
                </option>
              ))}
            </select>
            <ChevronDown size={15} />
          </div>
        </label>

        {error && <p className="home-error">{error}</p>}

        <section
          className="hero-risk-card"
          style={{
            borderColor: risk.accent,
            '--risk-glow': risk.accentSoft,
            background: `linear-gradient(180deg, ${risk.accentSoft} 0%, var(--color-surface) 70%)`,
          }}
        >
          <div className="hero-risk-top">
            <div className="hero-risk-icon" style={{ background: risk.gradient }}>
              <RiskIcon size={24} strokeWidth={2} color="#fff" />
            </div>
            <div className="hero-risk-top-text">
              <span className="hero-risk-chip" style={{ background: risk.accentSoft, color: risk.accent }}>
                {loading ? 'Kinakalkula...' : forecast?.risk_level || 'Walang Datos'}
              </span>
              <span className="hero-risk-window">2-Linggong Forecast</span>
            </div>
          </div>
          <h2>{forecast ? PEST_LABEL_FIL[forecast.pest] : dashboardSummary.pestFil}</h2>
          <p>
            {loading
              ? 'Kinukuha ang pinakabagong forecast mula sa BiLSTM na modelo...'
              : forecast
                ? RISK_MESSAGE_FIL[riskLevel]
                : 'Hindi pa available ang modelo para sa lugar na ito.'}
          </p>
        </section>

        <section className="tip-strip">
          <Lightbulb size={18} color="var(--color-accent-orange)" />
          <p>
            <strong>Payo:</strong> {dashboardSummary.tip}
          </p>
        </section>

        <section className="weather-strip">
          <div className="weather-strip-item">
            <Thermometer size={17} color="var(--color-accent-red)" />
            <div>
              <strong>
                {weather ? Math.round(weather.current.temperature_2m) : '--'}
                <small>°C</small>
              </strong>
              <span>Temp</span>
            </div>
          </div>
          <div className="weather-strip-divider" />
          <div className="weather-strip-item">
            <CloudRain size={17} color="#5b7fbf" />
            <div>
              <strong>
                {weather ? weather.current.precipitation : '--'}
                <small>mm</small>
              </strong>
              <span>Ulan</span>
            </div>
          </div>
          <div className="weather-strip-divider" />
          <div className="weather-strip-item">
            <Droplets size={17} color="var(--color-accent-yellow)" />
            <div>
              <strong>
                {weather ? Math.round(weather.current.relative_humidity_2m) : '--'}
                <small>%</small>
              </strong>
              <span>Halumigmig</span>
            </div>
          </div>
        </section>

        <section className="trend-card">
          <div className="trend-header">
            <h3>Pest Risk Trend</h3>
            <button className="trend-more" onClick={() => navigate('/alerts')}>
              Tingnan lahat <ChevronRight size={13} />
            </button>
          </div>
          <div className="trend-legend">
            <span><i style={{ background: LEVEL_COLOR[1] }} /> Ligtas</span>
            <span><i style={{ background: LEVEL_COLOR[2] }} /> Babala</span>
            <span><i style={{ background: LEVEL_COLOR[3] }} /> Panganib</span>
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
      </div>
    </div>
  );
}
