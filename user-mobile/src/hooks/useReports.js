import { useEffect, useState } from 'react';
import { fetchReports } from '../api/client';
import { pestGuide } from '../data/mockData';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { haversineKm } from '../utils/geo';
import { pestNames } from '../utils/pestNames';

// A sighting only signals an active threat for a couple of weeks — older
// ones are treated as resolved so stale pins don't make an area look infested.
const MAX_REPORT_AGE_DAYS = 14;
const MAX_REPORT_AGE_MS = MAX_REPORT_AGE_DAYS * 24 * 60 * 60 * 1000;

function isRecent(dateSpotted) {
  const t = new Date(dateSpotted).getTime();
  // An unparseable date is kept rather than silently dropped.
  return Number.isNaN(t) || Date.now() - t <= MAX_REPORT_AGE_MS;
}

const SEVERITY_LABEL = {
  low: 'Low Risk',
  medium: 'Medium Risk',
  high: 'High Risk',
};

// Farmers pick from a free-text-ish option like "Brown Planthopper
// (Kayumangging Hanip)"; match it against the guide by name so we can show
// a scientific name without asking the report form to carry one.
function matchPestGuide(pestType) {
  const needle = (pestType || '').toLowerCase();
  return pestGuide.find((p) => needle.includes(p.name.toLowerCase()) || needle.includes(p.nameFil.toLowerCase()));
}

function formatDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

// Fetches farmer-submitted sightings from the backend and shapes them into
// what the alerts list / map markers expect — RiskBadge levels, a distance
// from the logged-in farmer's own coordinates, and a matched scientific name.
export function useReports() {
  const { user } = useAuth();
  const { language, t } = useLanguage();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    fetchReports(user?.province)
      .then((records) => {
        if (cancelled) return;
        const shaped = records
          // Only LGU-verified sightings count as an active threat — a
          // pending or rejected report hasn't been corroborated and
          // shouldn't alarm nearby farmers (it also never nudges the
          // forecast; see server-python/app/decision/report_anchor.py,
          // which applies the same verified-only rule server-side).
          .filter((r) => r.status === 'verified' && isRecent(r.date_spotted))
          .map((r) => {
            const guide = matchPestGuide(r.pest_type);
            const hasCoords = user?.latitude != null && r.latitude != null && r.longitude != null;
            const distanceKm = hasCoords
              ? Math.round(haversineKm(user.latitude, user.longitude, r.latitude, r.longitude))
              : null;
            const names = guide
              ? pestNames(guide, language)
              : { primary: r.pest_type, secondary: '' };
            return {
              id: r.id,
              risk: r.severity,
              riskLabel: SEVERITY_LABEL[r.severity] || 'Unknown Risk',
              distance: distanceKm != null ? `${distanceKm}km` : t('alertsDistanceUnknown'),
              date: formatDate(r.date_spotted),
              distanceKm,
              pestName: names.primary,
              pestNameAlt: names.secondary,
              scientificName: guide?.scientificName || '—',
              location: r.municipality || r.province,
              description: r.notes || t('alertsNoDetails'),
              latitude: r.latitude,
              longitude: r.longitude,
              // "pending" until an LGU technician reviews it in admin-web —
              // only a "verified" report has actually influenced the
              // forecast (see server-python/app/decision/report_anchor.py).
              status: r.status || 'pending',
            };
          })
          .sort((a, b) => (a.distanceKm ?? Infinity) - (b.distanceKm ?? Infinity));
        setReports(shaped);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || t('alertsError'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [user, language]);

  return { reports, loading, error };
}
