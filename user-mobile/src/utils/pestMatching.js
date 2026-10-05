// Mirrors server-python/app/decision/pest_matching.py's PEST_KEYWORDS exactly
// — keep the two in sync. Used client-side only for UI decisions (e.g. which
// unit label to show); the backend's own derive_pest_code() is still the
// source of truth for what gets stored as pest_code.
const PEST_KEYWORDS = {
  BPH: ['brown planthopper', 'kayumangging hanip'],
  RSB: ['stem borer', 'aksip', 'atip'],
};

export function derivePestCode(pestType) {
  if (!pestType) return null;
  const needle = pestType.toLowerCase();
  for (const [code, keywords] of Object.entries(PEST_KEYWORDS)) {
    if (keywords.some((keyword) => needle.includes(keyword))) return code;
  }
  return null;
}
