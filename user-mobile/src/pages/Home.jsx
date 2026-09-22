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
import { useLanguage } from '../context/LanguageContext';
import { useReports } from '../hooks/useReports';
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

export default function Home() {
  const navigate = useNavigate();
  const { user, growthStage, logout } = useAuth();
  const { language, t } = useLanguage();
  const { reports } = useReports();
  const [weather, setWeather] = useState(null);
  const [weatherUpdatedAt, setWeatherUpdatedAt] = useState(null);
  // Both pests' forecasts are kept (not just the worse one) so the risk
  // card can cycle between them — see the cycling effect below.
  const [forecasts, setForecasts] = useState({ BPH: null, RSB: null });
  const [activePest, setActivePest] = useState('BPH');
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
        const [bphForecast, rsbForecast, trajectory] = await Promise.all([
          fetchPestForecast(user.municipality, 'BPH', growthStage),
          fetchPestForecast(user.municipality, 'RSB', growthStage),
          fetchPestForecastTrajectory(user.municipality, 'BPH', growthStage, 7),
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

        if (trajectory.status === 'ok' && trajectory.points.length) {
          setTrend(
            trajectory.points.map((p) => ({
              day: new Date(p.date).toLocaleDateString('en-US', { weekday: 'short' }),
              level: (RISK_RANK[p.risk_level] ?? 0) + 1,
            }))
          );
        }
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

  // Alternates the risk card between BPH and RSB every 10s. Only runs once
  // both forecasts have actually loaded — a single available pest (or
  // still loading) just stays put.
  useEffect(() => {
    if (!forecasts.BPH || !forecasts.RSB) return;
    const intervalId = setInterval(() => {
      setActivePest((prev) => (prev === 'BPH' ? 'RSB' : 'BPH'));
    }, RISK_CARD_CYCLE_MS);
    return () => clearInterval(intervalId);
  }, [forecasts.BPH, forecasts.RSB]);

  const forecast = forecasts[activePest] || forecasts.BPH || forecasts.RSB;
  const bothPestsAvailable = Boolean(forecasts.BPH && forecasts.RSB);
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
          <h1>{user?.province || currentLocation.province}</h1>
          <p>
            {t('homeLocationSubtitle')} {user?.municipality || currentLocation.region}
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
            <h2>
              {forecast
                ? t(`pestLabel${forecast.pest === 'BPH' ? 'Bph' : 'Rsb'}`)
                : language === 'en'
                  ? dashboardSummary.pestEn
                  : dashboardSummary.pestFil}
            </h2>
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
            <h3>{t('homeTrendTitle')}</h3>
            <div className="trend-legend">
              <span><i style={{ background: LEVEL_COLOR[1] }} /> {t('homeTrendSafe')}</span>
              <span><i style={{ background: LEVEL_COLOR[2] }} /> {t('homeTrendWarning')}</span>
              <span><i style={{ background: LEVEL_COLOR[3] }} /> {t('homeTrendDanger')}</span>
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
              <strong>{nearbyZones.length} {t('homeNearbyZones')}</strong>
              <small>
                {nearbyZones.join(' & ')} · {t('homeWithin')} {nearbyMaxKm}km
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
