# PestWatcher PH — Frontend

Mobile-shell web app for the thesis *"An Explainable Multimodal Temporal Deep Learning Framework with Biologically-Informed Climate Feature Engineering for Early Rice Pest Outbreak Prediction."*

This is the farmer-facing client only: a React + Vite single-page app that simulates a phone screen in the browser. It has **no real backend yet** — all pest detection, risk levels, and forecasts are mock data in [`src/data/mockData.js`](src/data/mockData.js), standing in for the future FastAPI/TensorFlow service described in [`../backend/README.md`](../backend/README.md).

---

## 1. Requirements

- **Node.js 18 or newer** (Node 20 LTS recommended) — check with `node -v`
- **npm** (comes with Node) — check with `npm -v`
- A modern browser (Edge, Chrome, or Firefox)
- To test the **live camera on a phone**: a phone and computer on the **same Wi-Fi network**

---

## 2. Install

From the `frontend/` folder:

```bash
npm install
```

This installs React 19, React Router 7, Recharts, Lucide icons, and the Vite dev tooling.

---

## 3. Run it locally (desktop browser)

```bash
npm run dev
```

Vite will print a local URL, and the dev server is also configured to auto-open your browser. Because HTTPS is enabled by default (see [Section 5](#5-camera-testing-on-a-real-phone)), your browser will show a certificate warning the first time — this is expected for a locally-generated self-signed cert. Click **Advanced → Proceed** (wording varies by browser) to continue.

The app opens on the **Welcome** screen. Use the bottom navigation to reach **Home**, **Regional Alerts**, and **Farmer's Guide**; tap the green camera FAB on Home to reach **AI Pest Scan**.

Stop the server anytime with `Ctrl+C` in the terminal.

---

## 4. Available scripts

Run these from inside `frontend/`:

| Command | What it does |
|---|---|
| `npm run dev` | Starts the Vite dev server with hot-reload, on HTTPS, exposed to your LAN |
| `npm run build` | Type-checks nothing (JS only) and builds an optimized production bundle into `dist/` |
| `npm run preview` | Serves the production build from `dist/` locally, to sanity-check the built output |
| `npm run lint` | Runs `oxlint` over the codebase |

---

## 5. Camera testing on a real phone

The **AI Pest Scan** screen uses the browser's real camera (`getUserMedia`), not a mock. Mobile browsers only allow camera access on secure origins (`https://` or `localhost`), so the dev server is pre-configured for this:

- [`vite.config.js`](vite.config.js) enables `@vitejs/plugin-basic-ssl` (a self-signed HTTPS certificate) and sets `server.host = true`, which exposes the dev server on your machine's LAN IP instead of only `localhost`.

**Steps:**

1. Make sure your phone and computer are connected to the **same Wi-Fi network**.
2. Run `npm run dev` on your computer.
3. Find your computer's LAN IP address:
   - Windows: open a terminal and run `ipconfig`, look for **IPv4 Address** (e.g. `192.168.1.138`)
4. On your phone's browser, go to:
   ```
   https://<your-lan-ip>:5173
   ```
   Example: `https://192.168.1.138:5173`
5. Your phone will warn that the certificate isn't trusted (self-signed cert) — this is expected. Tap **Advanced/Details → Proceed anyway / Visit site**.
6. Navigate to **AI Pest Scan** and allow camera access when prompted. You should see a live rectangular camera preview with a shutter button.

> **Note:** Screen mirroring tools like Live Share do **not** work for this — they only mirror your editor, not a real browser/camera session on the phone's own network stack. You must open the URL directly in the phone's browser as above.

If the camera doesn't start, check that:
- You accepted the certificate warning (an untrusted cert silently blocks `getUserMedia`)
- No other app/tab is already using the camera
- You allowed the camera permission prompt (check the site's permissions if you accidentally denied it)

---

## 6. Project structure

```
frontend/
├── src/
│   ├── main.jsx                # App entry point, mounts <App /> with HashRouter
│   ├── App.jsx                 # Central router; hosts global fixed UI
│   │                             (StatusBar, BottomNav, HomeFab, AlertsFab)
│   ├── index.css                # Design tokens (colors, radii, shadows) + device-frame shell
│   │
│   ├── pages/                   # One folder-flat file per screen
│   │   ├── Welcome.jsx/.css
│   │   ├── Home.jsx/.css                # Dashboard: risk hero card, 7-day trend, weather
│   │   ├── ScanCapture.jsx/.css         # Live camera capture (AI Pest Scan)
│   │   ├── ScanAnalyzing.jsx/.css       # Standalone analyzing screen (legacy route)
│   │   ├── ScanGallery.jsx/.css         # Pick a photo from device gallery instead of camera
│   │   ├── ScanResult.jsx/.css          # Prediction result: pest ID, 14-day forecast, ETL basis
│   │   ├── Alerts.jsx/.css              # Regional Alerts list + embedded weather map
│   │   ├── MapExpanded.jsx/.css         # Fullscreen weather map view
│   │   ├── Guide.jsx/.css               # Farmer's Guide / pest encyclopedia list
│   │   ├── GuideDetail.jsx/.css         # Single pest/disease/practice detail screen
│   │   └── ManualReport.jsx/.css        # Manual community sighting report form
│   │
│   ├── components/               # Shared UI building blocks
│   │   ├── StatusBar.jsx                # Fake phone status bar (time/signal/battery)
│   │   ├── ScreenHeader.jsx/.css        # Reusable page header (title + back button)
│   │   ├── BottomNav.jsx/.css           # Bottom tab bar (Home / Alerts / Guide)
│   │   ├── HomeFab.jsx/.css             # Floating camera button (Home → Scan)
│   │   ├── AlertsFab.jsx/.css           # Floating "+" button (Alerts → Manual Report)
│   │   ├── RiskBadge.jsx                # Small colored Low/Medium/High pill
│   │   └── WeatherMap.jsx/.css          # Windy.com embedded weather map iframe
│   │
│   ├── data/
│   │   ├── mockData.js                  # ALL mock content + thesis ETL logic (see below)
│   │   └── pestIcons.jsx                # Maps pest IDs to real photos or fallback icons
│   │
│   └── assets/                   # Images (logo, rice field photo, pest photos)
│
├── vite.config.js                # Dev server config (HTTPS + LAN exposure)
├── package.json
└── index.html
```

---

## 7. How the mock prediction data works

Since there's no real ML backend yet, [`src/data/mockData.js`](src/data/mockData.js) hardcodes everything the future `/api/predict` endpoint would return, grounded in the thesis's actual Table 2 Economic Threshold Level (ETL) values for **Brown Planthopper (BPH)** and **Rice Stem Borer (RSB)** — the only two pests the thesis's model targets.

Key pieces:

- **`etlThresholds`** — the exact low/medium boundary numbers per pest, per crop growth stage (Vegetative vs. Reproductive), taken directly from the thesis.
- **`classifyRisk(pestId, cropStage, measurement)`** — applies those thresholds to return `'low' | 'medium' | 'high'`.
- **`buildForecast(startRisk, peakRisk, peakDayIndex)`** — generates a 14-day array of daily risk levels, simulating a BiLSTM-style trajectory (risk builds toward a peak day) instead of one flat number.
- **`scanDetectionByRisk`** — three ready-made scenarios (`low`, `medium`, `high`), each with a pest, crop stage, measurement, confidence score, and a full 14-day forecast.

### Previewing each risk state

The **Scan Result** screen normally always shows the `medium` scenario (there's no real prediction to react to yet). To preview any of the three states without going through the camera flow, add a `?risk=` query parameter to the URL's hash route:

```
#/scan/result?risk=low
#/scan/result?risk=medium
#/scan/result?risk=high
```

This is a **development-only convenience**. In production, the risk level will come directly from the backend's prediction response instead of this URL parameter.

---

## 8. Design system notes

- The whole app renders inside a fixed **390×844px `.device-frame`** centered in the browser, simulating a phone viewport regardless of actual window size.
- Colors, spacing, and radii are all CSS custom properties defined in [`src/index.css`](src/index.css) under `:root` (`--color-primary`, `--color-accent-yellow`, `--color-accent-red`, `--radius-lg`, etc.) — reuse these variables rather than hardcoding new colors.
- Fixed UI that must survive scrolling (status bar, bottom nav, floating action buttons) is rendered as a **sibling of the scrollable page content in `App.jsx`**, never nested inside an individual page component. Nesting it inside a scrollable page will cause it to scroll away.
- UI copy is bilingual Filipino/English ("Taglish"), matching how the target farmer users actually speak.

---

## 9. Known gaps vs. the thesis (by design, at this stage)

This frontend intentionally does **not** yet include:

- A real image classification or BiLSTM forecasting model (mock data only)
- Real weather/climate feature ingestion (Home's weather strip is static mock data)
- An explainability (SHAP/LIME) visualization layer
- A live backend of any kind — see [`../backend/README.md`](../backend/README.md) for the planned API contract

These are expected to be built server-side in a future phase and consumed by this same frontend through the documented `/api/predict` contract.
