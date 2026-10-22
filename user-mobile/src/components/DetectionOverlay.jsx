import './DetectionOverlay.css';

// The scanned photo with a box on every planthopper the detector found
// (server-python/app/models/planthopper_detector.py). Boxes are in pixels of
// the uploaded photo, so the SVG uses the photo's own size as its viewBox and
// scales with the image.
function DetectionOverlay({ photo, detections, width, height, t }) {
  if (!photo || !detections?.length || !width || !height) return null;
  const stroke = Math.max(2, Math.round(Math.max(width, height) / 220));
  return (
    <section className="scan-result-signal detection-overlay">
      <span className="scan-result-signal-label">
        {t('scanResultDetectionTitle').replace('{count}', detections.length)}
      </span>
      <div className="detection-overlay-frame">
        <img src={photo} alt={t('scanCapturedAlt')} />
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
          {detections.map((d, i) => (
            <rect
              key={i}
              x={d.x0}
              y={d.y0}
              width={d.x1 - d.x0}
              height={d.y1 - d.y0}
              fill="none"
              stroke="#d64541"
              strokeWidth={stroke}
              rx={stroke}
            />
          ))}
        </svg>
      </div>
    </section>
  );
}

export default DetectionOverlay;
