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
  Bell,
  Camera,
  LogOut,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';
import { currentLocation, dashboardSummary } from '../data/mockData';
import { fetchWeatherForecast, fetchPestForecast, fetchPestForecastTrajectory } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';
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

const RISK_RANK = { Low: 0, Medium: 1, High: 2 };
const WEATHER_REFRESH_MS = 2 * 60 * 1000;
const RISK_CARD_CYCLE_MS = 10 * 1000;
const PEST_META = {
  BPH: { labelKey: 'pestLabelBph', trendTitleKey: 'homeTrendTitleBph' },
  RSB: { labelKey: 'pestLabelRsb', trendTitleKey: 'homeTrendTitleRsb' },
};

// Two weeks, matching the model's 14-day forecast window.
const TREND_DAYS = 14;

// Two-line axis label (weekday over date) so 14 slim bars stay readable;
// falls back to the plain `day` text for the static mock data.
function TrendTick({ x, y, payload, data }) {
  const item = data[payload.index];
  return (
    <g transform={`translate(${x},${y})`}>
      <text dy={12} textAnchor="middle" fontSize={10} fill="var(--color-text-muted)">
        {item?.dow ?? item?.day}
      </text>
      {item?.dom != null && (
        <text dy={24} textAnchor="middle" fontSize={9} fill="var(--color-text-muted)" opacity={0.7}>
          {item.dom}
        </text>
      )}
    </g>
  );
}

export default function Home() {
  const navigate = useNavigate();
  const { user, growthStage, logout } = useAuth();
  const { language, t } = useLanguage();
  const [weather, setWeather] = useState(null);
  const [weatherUpdatedAt, setWeatherUpdatedAt] = useState(null);
  // Both pests' forecasts and trends are kept (not just the worse one) so
  // the single risk card + single trend chart below can cycle between them
  // together, on the same interval and the same active pest.
  const [forecasts, setForecasts] = useState({ BPH: null, RSB: null });
  const [trends, setTrends] = useState({ BPH: null, RSB: null });
  const [activePest, setActivePest] = useState('BPH');
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
        if (!cancelled) setError(err.message || t('homeWeatherError'));
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
        const [bphForecast, rsbForecast, bphTrajectory, rsbTrajectory] = await Promise.all([
          fetchPestForecast(user.municipality, 'BPH', growthStage),
          fetchPestForecast(user.municipality, 'RSB', growthStage),
          fetchPestForecastTrajectory(user.municipality, 'BPH', growthStage, TREND_DAYS),
          fetchPestForecastTrajectory(user.municipality, 'RSB', growthStage, TREND_DAYS),
        ]);
        if (cancelled) return;

        const nextForecasts = {
          BPH: bphForecast.status === 'ok' ? { pest: 'BPH', ...bphForecast } : null,
          RSB: rsbForecast.status === 'ok' ? { pest: 'RSB', ...rsbForecast } : null,
        };
        setForecasts(nextForecasts);

        // Lead with whichever pest is currently riskier — the cycling
        // effect below then alternates to the other one every 10s.
        if (nextForecasts.BPH && nextForecasts.RSB) {
          setActivePest(
            (RISK_RANK[nextForecasts.RSB.risk_level] ?? -1) >
              (RISK_RANK[nextForecasts.BPH.risk_level] ?? -1)
              ? 'RSB'
              : 'BPH'
          );
        } else if (nextForecasts.BPH) {
          setActivePest('BPH');
        } else if (nextForecasts.RSB) {
          setActivePest('RSB');
        }

        const toTrend = (trajectory) =>
          trajectory.status === 'ok' && trajectory.points.length
            ? trajectory.points.map((p) => {
                const date = new Date(`${p.date}T00:00:00`);
                return {
                  key: p.date,
                  dow: date.toLocaleDateString('en-US', { weekday: 'short' }).slice(0, 2),
                  dom: date.getDate(),
                  level: (RISK_RANK[p.risk_level] ?? 0) + 1,
                };
              })
            : null;

        setTrends({
          BPH: toTrend(bphTrajectory),
          RSB: toTrend(rsbTrajectory),
        });
      } catch (err) {
        if (!cancelled) setError(err.message || t('homeForecastError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadForecast();
    return () => {
      cancelled = true;
    };
  }, [user, growthStage]);

  // Alternates both the risk card and the trend chart between BPH and RSB
  // together, every 10s — a single activePest drives both, so they never
  // fall out of sync. Only runs once both forecasts have actually loaded.
  useEffect(() => {
    if (!forecasts.BPH || !forecasts.RSB) return;
    const intervalId = setInterval(() => {
      setActivePest((prev) => (prev === 'BPH' ? 'RSB' : 'BPH'));
    }, RISK_CARD_CYCLE_MS);
    return () => clearInterval(intervalId);
  }, [forecasts.BPH, forecasts.RSB]);

  const forecast = forecasts[activePest];
  const bothPestsAvailable = Boolean(forecasts.BPH && forecasts.RSB);
  const riskLevel = forecast?.risk_level?.toLowerCase() || 'low';
  const risk = RISK_META[riskLevel] || RISK_META.low;
  const RiskIcon = risk.icon;
  const trendData = trends[activePest] || dashboardSummary.trend;
  const now = new Date();
  const dateTimeLabel = `${now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${now.toLocaleTimeString(
    'en-US',
    { hour: '2-digit', minute: '2-digit', hour12: true }
  )}`;

  return (
    <div className="home-screen">
      <div className="home-hero hero-surface">
        <div className="home-topbar">
          <span className="home-brand">
            <img src={logoImg} alt="" className="home-brand-logo" /> PESTWATCHER<sup>PH</sup>
          </span>
          <span className="home-topbar-right">
            <LanguageToggle />
            <span className="home-datetime">{dateTimeLabel}</span>
            <button className="home-logout" onClick={() => { logout(); navigate('/'); }} aria-label="Logout">
              <LogOut size={12} />
            </button>
          </span>
        </div>

        <div className="home-location">
          <h1>{user?.municipality || currentLocation.region}</h1>
          <p>
            {user?.province || currentLocation.province} &middot; {t('homeLocationSubtitle')}
          </p>
        </div>
      </div>

      <div className="home-body">
        {error && <p className="home-error">{error}</p>}

        <section className="hero-risk-card">
          <div className="hero-risk-content" key={activePest}>
            <div className="hero-risk-top">
              <div className="hero-risk-icon" style={{ borderColor: risk.accent, color: risk.accent }}>
                <RiskIcon size={22} strokeWidth={2} />
              </div>
              <span className="hero-risk-chip" style={{ background: risk.accentSoft, color: risk.accent }}>
                {loading ? t('homeCalculating') : t(`riskLabel${riskLevel[0].toUpperCase()}${riskLevel.slice(1)}`)}
              </span>
              {bothPestsAvailable && (
                <div className="hero-risk-dots" aria-hidden="true">
                  <span className={activePest === 'BPH' ? 'is-active' : ''} />
                  <span className={activePest === 'RSB' ? 'is-active' : ''} />
                </div>
              )}
            </div>
            <h2>{t(PEST_META[activePest].labelKey)}</h2>
            <p>
              {loading
                ? t('homeForecastLoading')
                : forecast
                  ? t(`riskMessage${riskLevel[0].toUpperCase()}${riskLevel.slice(1)}`)
                  : t('homeForecastUnavailable')}
            </p>
          </div>

          <div className="hero-risk-divider" />

          <div className="hero-risk-tip">
            <Lightbulb size={16} color="var(--color-accent-orange)" />
            <p>
              <strong>{t('homeFarmerTip')}</strong> {language === 'en' ? dashboardSummary.tipEn : dashboardSummary.tip}
            </p>
          </div>
        </section>

        <section className="weather-tiles-block">
          <div className="weather-tiles-live">
            <span className="weather-tiles-live-dot" />
            {t('homeWeatherLive')} {weatherUpdatedAt ? `· ${t('homeWeatherUpdated')} ${weatherUpdatedAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}` : ''}
          </div>
          <div className="weather-tiles">
            <div className="weather-tile">
              <div className="weather-tile-top">
                <span>{t('homeTempLabel')}</span>
                <Thermometer size={16} color="var(--color-accent-red)" />
              </div>
              <strong>{weather ? Math.round(weather.current.temperature_2m) : '--'}°C</strong>
              <span className="weather-tile-caption">
                {weather ? `${t('homeTempFeels')} ${Math.round(weather.current.apparent_temperature ?? weather.current.temperature_2m)}°C` : '--'}
              </span>
            </div>
            <div className="weather-tile">
              <div className="weather-tile-top">
                <span>{t('homeRainfallLabel')}</span>
                <CloudRain size={16} color="#5b7fbf" />
              </div>
              <strong>{weather ? weather.current.precipitation.toFixed(1) : '--'} mm</strong>
              <span className="weather-tile-caption">{t('homeRainfallNow')}</span>
            </div>
            <div className="weather-tile">
              <div className="weather-tile-top">
                <span>{t('homeHumidityLabel')}</span>
                <Droplets size={16} color="var(--color-primary)" />
              </div>
              <strong>{weather ? Math.round(weather.current.relative_humidity_2m) : '--'}%</strong>
              <span className="weather-tile-caption">
                {weather && weather.current.relative_humidity_2m >= 80 ? t('homeHumidityHigh') : t('homeHumidityNormal')}
              </span>
            </div>
          </div>
        </section>

        <section className="trend-card">
          <div className="trend-header">
            <h3>{t(PEST_META[activePest].trendTitleKey)}</h3>
            <div className="trend-legend">
              <span><i style={{ background: LEVEL_COLOR[1] }} /> {t('homeTrendSafe')}</span>
              <span><i style={{ background: LEVEL_COLOR[2] }} /> {t('homeTrendWarning')}</span>
              <span><i style={{ background: LEVEL_COLOR[3] }} /> {t('homeTrendDanger')}</span>
            </div>
          </div>
          <div className="trend-chart">
            <ResponsiveContainer width="100%" height={128}>
              <BarChart data={trendData} barCategoryGap="22%" margin={{ top: 4, right: 0, left: 0, bottom: 0 }} key={activePest}>
                <XAxis
                  dataKey={(d) => d.key ?? d.day}
                  axisLine={false}
                  tickLine={false}
                  interval={0}
                  height={32}
                  tick={<TrendTick data={trendData} />}
                />
                <YAxis hide domain={[0, 3]} />
                <Bar dataKey="level" radius={[5, 5, 2, 2]} minPointSize={6}>
                  {trendData.map((entry, i) => (
                    <Cell key={i} fill={LEVEL_COLOR[entry.level]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {trendData.length === TREND_DAYS && <span className="trend-week-divider" aria-hidden="true" />}
          </div>
        </section>

        <button className="nearby-alerts-link" onClick={() => navigate('/alerts')}>
          <Bell size={18} color="var(--color-primary)" />
          <span className="nearby-alerts-text">{t('homeViewNearbyAlerts')}</span>
          <ChevronRight size={16} color="var(--color-text-muted)" />
        </button>

        <button className="scan-strip" onClick={() => navigate('/scan')}>
          <span className="scan-strip-icon">
            <Camera size={18} />
          </span>
          <span className="scan-strip-text">
            <strong>{t('homeScanTitle')}</strong>
            <small>{t('homeScanSubtitle')}</small>
          </span>
          <ChevronRight size={16} color="var(--color-text-muted)" />
        </button>

        <div className="report-manual-block">
          <button className="report-manual-cta" onClick={() => navigate('/report')}>
            {t('homeReportCta')}
          </button>
          <p>{t('homeReportSubtitle')}</p>
        </div>
      </div>
    </div>
  );
}
