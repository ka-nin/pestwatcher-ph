# PestWatcher PH — Farmer Mobile App

Mobile-shell web app for the thesis *"An Explainable Multimodal Temporal Deep Learning Framework with Biologically-Informed Climate Feature Engineering for Early Rice Pest Outbreak Prediction."*

This is the farmer-facing client only: a React + Vite single-page app that simulates a phone screen in the browser. It is wired up to the real FastAPI backend ([`../server-python`](../server-python)) for login, weather, and BiLSTM pest-risk forecasts — see [Section 8](#8-backend-integration) for what's real vs. still mocked.

---

## 1. Requirements

- **Node.js 18 or newer** (Node 20 LTS recommended) — check with `node -v`
- **npm** (comes with Node) — check with `npm -v`
- A modern browser (Edge, Chrome, or Firefox)
- To test the **live camera on a phone**: a phone and computer on the **same Wi-Fi network**

---

## 2. Install

From the repository root (this is an npm workspace — installing from inside `user-mobile/` directly will not resolve correctly):

```bash
npm install
```

This installs React 19, React Router 7, Recharts, Lucide icons, and the Vite dev tooling.

---

## 3. Point it at the backend

Copy the example env file:

```bash
cp .env.example .env   # Windows: copy .env.example .env
```

This sets `VITE_API_URL=http://localhost:8000`. The backend ([`../server-python`](../server-python)) must be running for login, weather, and forecasts to work — see that folder's README for setup. Without `.env`, the app falls back to `http://localhost:8000` anyway (see [`src/api/client.js`](src/api/client.js)), but copying it explicitly makes the URL easy to change (e.g. pointing at a deployed backend).

---

## 4. Run it locally (desktop browser)

```bash
npm run dev
```

Vite will print a local URL, and the dev server is also configured to auto-open your browser. Because HTTPS is enabled by default (see [Section 6](#6-camera-testing-on-a-real-phone)), your browser will show a certificate warning the first time — this is expected for a locally-generated self-signed cert. Click **Advanced → Proceed** (wording varies by browser) to continue.

The app opens on the **Welcome** screen with a login form. Use the seeded demo farmer account (prefilled by default):

- Username: `farmer_demo`
- Password: `RicePest!Demo2026`

(Defined in `server-python/app/data/farmer_users.py` — this is the only account with real municipality coordinates, so it's the one guaranteed to return live weather/forecast data.)

After logging in, use the bottom navigation to reach **Home**, **Regional Alerts**, and **Farmer's Guide**; tap the green camera FAB on Home to reach **AI Pest Scan**.

Stop the server anytime with `Ctrl+C` in the terminal.

---

## 5. Available scripts

Run these from inside `user-mobile/`:

| Command | What it does |
|---|---|
| `npm run dev` | Starts the Vite dev server with hot-reload, on HTTPS, exposed to your LAN |
| `npm run build` | Type-checks nothing (JS only) and builds an optimized production bundle into `dist/` |
| `npm run preview` | Serves the production build from `dist/` locally, to sanity-check the built output |
| `npm run lint` | Runs `oxlint` over the codebase |

---

## 6. Camera testing on a real phone

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

Note: when testing on a phone this way, `VITE_API_URL` (see [Section 3](#3-point-it-at-the-backend)) still points at `localhost:8000`, which means "the phone itself" — not your computer. Login/weather/forecast calls will fail unless you change `.env` to your computer's LAN IP (e.g. `VITE_API_URL=http://192.168.1.138:8000`) and restart `npm run dev`, and add that same origin to the backend's `CORS_ORIGINS` (see `server-python/.env`).

---

## 7. Project structure

```
user-mobile/
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
│   │   ├── mockData.js                  # Pest guide content + thesis ETL logic (see below)
│   │   └── pestIcons.jsx                # Maps pest IDs to real photos or fallback icons
│   │
│   ├── api/
│   │   └── client.js             # fetch wrappers for every backend endpoint this app calls
│   │
│   ├── context/
│   │   └── AuthContext.jsx       # Logged-in user + selected growth stage, persisted to localStorage
│   │
│   └── assets/                   # Images (logo, rice field photo, pest photos)
│
├── vite.config.js                # Dev server config (HTTPS + LAN exposure)
├── .env.example                  # VITE_API_URL
├── package.json
└── index.html
```

---

## 8. Backend integration

All backend calls live in [`src/api/client.js`](src/api/client.js), which mirrors the pattern already used by `admin-web/src/lib/api.ts`. What's real vs. still a stub, per screen:

| Screen | Endpoint | Status |
|---|---|---|
| Welcome (login) | `POST /api/auth/login` | Real |
| Home (weather strip) | `GET /api/weather/forecast` | Real |
| Home (risk hero card + trend chart) | `GET /api/inference/forecast/live`, `GET /api/inference/forecast/trajectory` | Real — BiLSTM models for BPH and RSB, whichever currently reports the higher risk is shown |
| Scan → AI Pest Scan | `POST /api/inference/image` | Wired up and uploads the real captured/selected photo, but the backend's ResNet-50 image classifier is still an unimplemented stub (`server-python/app/models/resnet_model.py`) — every real scan currently lands on a "model hindi pa handa" screen instead of a result. The image is still saved server-side for future training. |
| Manual Report | `POST /api/reports` | Real — appends to `server-python/reports.json` |

Two things every forecast call needs, both sourced from app state rather than the backend:

- **`municipality`** — comes from the logged-in user (`AuthContext`). Only municipalities with coordinates in `server-python/app/data/lgu_users.py` will return real forecasts; today that's just `farmer_demo`'s "Science City of Muñoz".
- **`growth_stage`** — there's no way for weather data to infer this, so Home has a dropdown for it (Seedling/Tillering/Elongation/Panicle/Flowering/Ripening), persisted to `localStorage` and reused for every forecast call.

### The pest guide / ETL reference data is still local, on purpose

[`src/data/mockData.js`](src/data/mockData.js) still hardcodes the **Farmer's Guide** content (pest descriptions, signs, prevention tips) and the thesis's Table 2 Economic Threshold Level (ETL) values for **Brown Planthopper (BPH)** and **Rice Stem Borer (RSB)** — this is reference/encyclopedia content, not a prediction, so there's no backend endpoint for it (and doesn't need one).

- **`etlThresholds`** — the exact low/medium boundary numbers per pest, per crop growth stage (Vegetative vs. Reproductive), taken directly from the thesis.
- **`classifyRisk(pestId, cropStage, measurement)`** — applies those thresholds to return `'low' | 'medium' | 'high'`.
- **`scanDetectionByRisk`** — three ready-made scenarios (`low`, `medium`, `high`) used only as a design-preview fallback on Scan Result (see below), not as real prediction data anymore.

### Previewing each Scan Result risk state (design-only)

Since the real image classifier isn't trained yet, `ScanResult.jsx` still supports a `?risk=` override to preview all three risk states without a real detection:

```
#/scan/result?risk=low
#/scan/result?risk=medium
#/scan/result?risk=high
```

This only applies when the screen is opened directly (no real inference result in navigation state). A real scan through the camera flow always shows the actual backend response — currently the "model not ready" screen, until the ResNet-50 classifier is trained and wired up.

---

## 9. Design system notes

- The whole app renders inside a fixed **390×844px `.device-frame`** centered in the browser, simulating a phone viewport regardless of actual window size.
- Colors, spacing, and radii are all CSS custom properties defined in [`src/index.css`](src/index.css) under `:root` (`--color-primary`, `--color-accent-yellow`, `--color-accent-red`, `--radius-lg`, etc.) — reuse these variables rather than hardcoding new colors.
- Fixed UI that must survive scrolling (status bar, bottom nav, floating action buttons) is rendered as a **sibling of the scrollable page content in `App.jsx`**, never nested inside an individual page component. Nesting it inside a scrollable page will cause it to scroll away.
- UI copy is bilingual Filipino/English ("Taglish"), matching how the target farmer users actually speak.

---

## 10. Known gaps vs. the thesis (by design, at this stage)

This frontend intentionally does **not** yet include:

- A real image classification model behind AI Pest Scan — the request/response plumbing is real, but the backend's ResNet-50 classifier is still an unimplemented stub (see [`../server-python/README.md`](../server-python/README.md#adding-the-resnet-50-image-model))
- An explainability (SHAP/LIME) visualization layer — the backend already exposes `GET /api/inference/forecast/explain`, this app just doesn't render it anywhere yet
- Real persistence for manual reports beyond a flat JSON file (`server-python/reports.json`)
- Any municipality other than "Science City of Muñoz" returning real forecasts, since that's the only one with coordinates on file today

These are expected to be finished in a future phase; the mobile app's API layer ([`src/api/client.js`](src/api/client.js)) already matches the contract each of these will use once ready.
