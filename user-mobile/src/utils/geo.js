export function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Picks whichever option is geographically closest to (lat, lon).
// `getCoords` pulls [lat, lon] out of each option so this works for any
// shape (municipalities, reports, ...).
export function findNearest(lat, lon, options, getCoords) {
  let nearest = null;
  let nearestKm = Infinity;
  for (const option of options) {
    const [oLat, oLon] = getCoords(option);
    if (oLat == null || oLon == null) continue;
    const km = haversineKm(lat, lon, oLat, oLon);
    if (km < nearestKm) {
      nearestKm = km;
      nearest = option;
    }
  }
  return nearest ? { nearest, distanceKm: nearestKm } : null;
}
