import { useEffect, useState } from 'react';
import { fetchMunicipalitiesRisk } from '../api/client';
import { useLanguage } from '../context/LanguageContext';

const RISK_RANK = { High: 3, Medium: 2, Low: 1 };

// Worst-case of the two pests the model tracks — a municipality is only as
// "safe" as its riskiest pest, same convention the admin dashboard's
// high/medium-risk counts use (see admin-web OverviewPage.tsx).
function overallRisk(row) {
  const bph = row.bph.risk_level;
  const rsb = row.rsb.risk_level;
  if (!bph && !rsb) return null;
  if (!bph) return rsb;
  if (!rsb) return bph;
  return RISK_RANK[bph] >= RISK_RANK[rsb] ? bph : rsb;
}

// Fetches the public per-municipality BPH/RSB risk snapshot
// (/api/locations/municipalities/risk) and shapes it for the mobile
// alerts list — one row per municipality, worst-pest risk level, sorted
// highest-risk first with the farmer's own municipality pinned on top.
export function useMunicipalityRisk(ownMunicipality) {
  const { t } = useLanguage();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    fetchMunicipalitiesRisk()
      .then((data) => {
        if (cancelled) return;
        const shaped = (data.municipalities || [])
          .map((row) => ({
            municipality: row.municipality,
            province: row.province,
            risk: overallRisk(row),
            bphRisk: row.bph.risk_level,
            rsbRisk: row.rsb.risk_level,
          }))
          .sort((a, b) => {
            if (a.municipality === ownMunicipality) return -1;
            if (b.municipality === ownMunicipality) return 1;
            return (RISK_RANK[b.risk] || 0) - (RISK_RANK[a.risk] || 0);
          });
        setRows(shaped);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || t('alertsRiskFetchError'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ownMunicipality]);

  return { rows, loading, error };
}
