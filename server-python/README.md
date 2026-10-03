# server-python

FastAPI backend for the Rice Pest Forecasting System — replaces the legacy
`server` (Node/Express) workspace. Chosen so the ML pipeline (ResNet-50 for
optical field surveillance, BiLSTM for outbreak-timing forecasts) can live
natively in the same language/runtime as the models themselves, instead of
shelling out from Node.

## Setup

From this folder (Windows):

```
npm run setup
```

This creates a `.venv` virtual environment and installs `requirements.txt`
into it. On macOS/Linux, do it manually instead:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and adjust as needed (CORS origins, port).

## Database

Accounts (LGU, farmer, SuperAdmin) and farmer-submitted reports live in
PostgreSQL, not in-memory. Start it from the repo root before running the
backend:

```
docker compose up -d
```

`.env.example`'s `DATABASE_URL` already matches this container's default
credentials. On startup, `app/main.py` creates the tables (`app/db_models.py`)
if they don't exist and seeds them with the same demo accounts previously
hardcoded here. This is a no-op once real data exists. There's no migration
framework (Alembic) at this project's scope — schema changes during
development are handled by editing `app/db_models.py` and recreating the
dev database (`docker compose down -v && docker compose up -d`).

A legacy flat `reports.json` is still read once on first startup if the
`reports` table is empty (`migrate_from_json_if_empty`, `app/data/reports_store.py`)
so any pre-Postgres local dev data isn't lost — after that first run, every
report read/write goes through Postgres exclusively.

Farmer-uploaded photos still live on disk under `uploads/` (path only,
recorded in the `reports` table) — they were never moved into Postgres.

## Run

```
npm run dev
```

Starts Uvicorn with auto-reload on `http://localhost:8000`. Interactive API
docs are auto-generated at `http://localhost:8000/docs`.

At startup, `app/main.py` loads the trained BiLSTM **and** ResNet-50 weights
for both pests (BPH and RSB) from `ml/weights/`. If a pest's weights aren't
there yet (e.g. a fresh clone before training has been run), that pest's
forecast/image endpoints report `status: "model_not_loaded"` instead of
crashing the app — see `ml/bilstm/train.py` and `ml/resnet/train.py` below.

## Tests

```
.venv/Scripts/python.exe -m pytest tests/ -v
```

A small smoke-test suite (`tests/`, pytest + `httpx`'s `TestClient`) — health
check, login success/failure, the per-report auth fix's regression case, and
one live forecast call. Runs against the real dev database (`docker compose
up -d` first), not a separate test DB — there's no test-infra isolation at
this project's scope, so these are smoke tests proving the app boots and its
core paths work end to end, not a full correctness suite. The login-success
test reads a real seeded account from `credentials.txt` at the repo root at
test time and skips (not fails) if that file isn't present.

## Folder structure

```
server-python/
├── app/                       # the serving API — thin, no training code
│   ├── main.py                 # FastAPI app, CORS, router registration, startup model load
│   ├── config.py               # Settings loaded from .env (pydantic-settings)
│   ├── db.py / db_models.py    # SQLAlchemy engine/session + table definitions (Postgres)
│   ├── routers/
│   │   ├── auth.py             # POST /api/auth/login (LGU techs, farmers, SuperAdmin)
│   │   ├── admin.py            # SuperAdmin-only: LGU accounts, cross-municipality overview, model insights
│   │   ├── weather.py          # GET /api/weather/forecast (Open-Meteo), plus internal fetch helpers
│   │   ├── inference.py        # see "API endpoints" below
│   │   ├── locations.py        # public municipality list + risk overview (no auth)
│   │   └── reports.py          # farmer report CRUD, LGU verification, per-report gap analysis
│   ├── data/                    # Postgres-backed accessors (not hardcoded in-memory lists anymore)
│   │   ├── lgu_users.py          # also the coordinate lookup for live weather fetches
│   │   ├── farmer_users.py
│   │   ├── reports_store.py       # all report reads/writes — the `reports` table
│   │   └── municipalities.py      # canonical municipality/coordinate registry
│   ├── schemas/                  # Pydantic request/response models
│   ├── models/
│   │   ├── resnet_model.py        # ResNet-50 wrapper — trained and live, two binary classifiers (BPH, RSB)
│   │   └── bilstm_model.py        # BiLSTM wrapper — trained, loads real weights
│   ├── decision/
│   │   ├── etl_thresholds.py      # fixed, non-learned Low/Medium/High bucketing (thesis Table 2)
│   │   ├── report_anchor.py       # per-report "what if this report shifted the forecast" math — used only by gap analysis, never the live forecast (see below)
│   │   ├── gap_implication.py     # turns a gap analysis into a one-sentence plain-language summary
│   │   └── pest_matching.py       # free-text pest_type -> BPH/RSB code
│   └── preprocessing/
│       └── features.py             # GDD/CRF/HP/VPD/WSI/trend — canonical formulas, shared
│                                    #   between training (ml/) and inference (app/)
│
├── ml/                          # training pipeline — separate from the serving app
│   ├── config.py                 # per-pest params (T_base, CRF window, RH threshold), paths
│   ├── validity_test.py          # post-training pass/fail check — statistical (R²/MAE) + field (gap-analysis agreement)
│   ├── datasets/
│   │   ├── raw/                   # gitignored — untouched weather_raw.csv / pest_raw.csv
│   │   ├── cleaning/
│   │   │   └── clean_timeseries.py # dedupe, fix sensor errors, interpolate gaps, merge
│   │   └── processed/              # gitignored — cleaned CSV + built sequences (.npz)
│   ├── bilstm/
│   │   ├── build_sequences.py      # cleaned CSV (+ ingested reports) -> (X_sequence, X_static, y) per pest
│   │   ├── train.py                # trains + evaluates (RMSE/MAE/R²), saves to ml/weights/
│   │   ├── export_insights.py      # per-sample predictions + SHAP summary for admin-web's Model Insights page
│   │   └── ingest_reports.py       # pulls verified farmer reports into a report-derived training CSV — see "Continuous learning" below
│   ├── resnet/                     # image classifier training — trained, weights exist
│   │   ├── crops.py / augment.py    # bounding-box crop extraction + augmentation from annotated source images
│   │   ├── prepare_dataset.py       # builds the binary (pest vs. not-pest) train/val/test split per pest
│   │   ├── train.py                 # transfer learning on ResNet-50, saves .keras + test metrics
│   │   └── evaluate.py / evaluate_grid.py
│   ├── explainability/
│   │   └── shap_report.py          # SHAP GradientExplainer over the trained BiLSTM
│   └── weights/
│       ├── bph/                     # bilstm_bph.keras + resnet50_bph.keras + scalers + test metrics
│       └── rsb/                     # bilstm_rsb.keras + resnet50_rsb.keras + scalers + test metrics
│
├── uploads/                    # Field images land here (gitignored)
├── requirements.txt
├── .env.example
└── package.json                # so `npm run dev -w server-python` works from root
```

## API endpoints

| Endpoint | Auth | What it does |
|---|---|---|
| `GET /api/health` | — | Liveness check |
| `POST /api/auth/login` | — | LGU tech, farmer, and SuperAdmin accounts |
| `GET /api/weather/forecast` | — | Forward-looking weather (Open-Meteo), used by the dashboard's Climate Drivers charts |
| `POST /api/inference/image` | — | ResNet-50 image classification — two binary classifiers (BPH, RSB), returns whichever fires strongest |
| `POST /api/inference/forecast` | — | BiLSTM forecast from a caller-supplied 14-day weather window |
| `GET /api/inference/forecast/live` | — | Same, but fetches the real past 14 days for a municipality itself |
| `GET /api/inference/forecast/trajectory` | — | Up to 14 sequential daily forecasts (for charting a curve) — works from only past weather, since horizon ≥ days requested |
| `GET /api/inference/forecast/explain` | — | SHAP feature attributions for the same live prediction `/forecast/live` would return |
| `GET /api/reports` | — | Farmer-submitted sightings, filterable by province/municipality |
| `POST /api/reports` | — | Farmer manual pest-sighting report (user-mobile), optional photo (runs the ResNet-50 classifier) |
| `PATCH /api/reports/{id}` | LGU | Verify or reject a report — scoped to the technician's own municipality; `verified_by` is taken from the token, never the request body |
| `GET /api/reports/{id}/gap-analysis` | — | For one verified report: 14-day weather-only forecast vs. what it would look like if this report anchored it, plus a plain-language implication (`app/decision/gap_implication.py`) |
| `GET /api/reports/deleted` | LGU | Soft-deleted reports audit trail, own municipality only |
| `DELETE /api/reports/{id}` | LGU | Soft-delete a report, own municipality only |
| `GET /api/locations/municipalities` | — | Public list of covered municipalities (mobile app's picker) |
| `GET /api/locations/municipalities/risk` | — | Public live BPH/RSB risk per municipality |
| `GET /api/admin/lgu-users`, `POST`, `PATCH`, `DELETE` | SuperAdmin | LGU account management |
| `GET /api/admin/overview` | SuperAdmin | Live BPH/RSB forecast for every municipality on file |
| `GET /api/admin/etl-thresholds` | SuperAdmin | Read-only view of the fixed ETL bands |
| `GET /api/admin/model-insights` | SuperAdmin | Saved test metrics, SHAP summaries, and prediction samples for both model families |

All forecast endpoints return a **continuous value** (hoppers/hill or %
damage) as the primary output, with the Low/Medium/High risk level as a
*derived* secondary field from `app/decision/etl_thresholds.py` — the model
predicts, ETL only buckets. See that module's docstring for why the split
matters.

**Verified farmer reports never change a live forecast.** An earlier
version of this system let a verified report shift `/forecast/live` and
`/forecast/trajectory` toward the reported value for a fading window
(`app/decision/report_anchor.py`). That adjustment has been removed —
today's prediction is always the plain weather-driven model output. A
verified report instead (a) is compared against the model after the fact
via `GET /api/reports/{id}/gap-analysis`, using the same anchor/fade math
purely as a read-only comparison, and (b) becomes training data for the
next periodic retrain (see "Continuous learning" below). This keeps "what
the farmer sees today" and "what the farmer reported" cleanly separated.

## The BiLSTM pipeline, end to end

1. **Raw data** → `ml/datasets/raw/{weather,pest}_raw.csv` (synthetic, generated to spec — see thesis Sources of Data; not yet real PhilRice/PAGASA records).
2. **Clean**: `python -m ml.datasets.cleaning.clean_timeseries` → dedupes, fixes sensor errors, interpolates gaps, merges into `ml/datasets/processed/weather_pest_daily_clean.csv` + a `cleaning_report.json` you can cite directly.
3. **Ingest verified reports** (optional, for a periodic retrain — see "Continuous learning" below): `python -m ml.bilstm.ingest_reports` → folds LGU-verified farmer reports into a second CSV that step 4 merges in automatically.
4. **Build sequences**: `python -m ml.bilstm.build_sequences` → per-pest `.npz` files (14-day sequence features + static aggregate features + regression target), using per-pest parameters from `ml/config.py`.
5. **Train**: `python -m ml.bilstm.train --pest BPH` (and `--pest RSB`) → chronological 70/15/15 split with a purge gap (not random — sequences overlap, so a random split would leak), saves `.keras` weights + scalers + test metrics to `ml/weights/{pest}/`.
6. **Validate**: `python -m ml.validity_test` → re-checks the saved test metrics against a minimum R²/MAE bar, and separately checks live predictions against verified reports via the same comparison `GET /api/reports/{id}/gap-analysis` exposes. Prints a pass/fail per pest.
7. **Serve**: `app/main.py` loads those weights at startup; `app/models/bilstm_model.py` rebuilds the same features at inference time from live weather.
8. **Explain**: `ml/explainability/shap_report.py` — a `GradientExplainer` against a background sample from the pest's own training sequences, cached per pest after first use.

To retrain after changing feature engineering or getting new data, rerun
steps 2, 4, and 5 in order (step 3 only if you want that retrain to include
newly verified reports) — each stage's output feeds the next.

## The ResNet-50 pipeline, end to end

1. **Source images** → `ml/resnet/{bph,sb,negative}/` (Roboflow-exported, annotated with bounding boxes), gitignored — too large for the repo.
2. **Crop**: `ml/resnet/crops.py` cuts each annotated box out (with padding) into its own image file, from pre-existing annotations — not a runtime object detector.
3. **Prepare dataset**: `python -m ml.resnet.prepare_dataset` → builds a binary (that pest vs. everything else) train/val/test split per pest, keeping crops from the same source image together so the split doesn't leak near-duplicates across train/test.
4. **Train**: `python -m ml.resnet.train --pest BPH` (and `--pest RSB`) → transfer learning on ImageNet-pretrained ResNet-50, two-phase (frozen head, then partial fine-tune), saves `.keras` weights + test metrics to `ml/weights/{pest}/`.
5. **Serve**: `app/main.py` loads both pests' weights at startup; a photo is run through both binary classifiers, whichever reports the higher positive confidence wins (see `app/models/resnet_model.py`'s module docstring).

Weight files (`resnet50_{pest}.keras`, ~200MB each) are gitignored — share
them out-of-band (see the comment in `.gitignore`) rather than via git.

## Continuous learning: how a verified report actually changes the system

A verified report never edits a live prediction (see the API table above).
Instead:

1. An LGU technician verifies a report (`PATCH /api/reports/{id}`).
2. Periodically — monthly, or sooner if enough new reports accumulate (see
   `ml/bilstm/ingest_reports.py`'s `REPORT_COUNT_THRESHOLD`) — someone runs
   `python -m ml.bilstm.ingest_reports`, which pulls every verified report
   and writes a report-derived training CSV.
3. `python -m ml.bilstm.build_sequences` merges that CSV into the training
   set (a report-derived row wins over the historical dataset's own value
   for the same municipality + date, since it's more direct ground truth).
4. `python -m ml.bilstm.train --pest <BPH|RSB>` retrains on the combined
   data, and `python -m ml.validity_test` checks whether the new model
   actually improved before it replaces the deployed weights.

This is a manual/scheduled runbook, not an automated pipeline — there's no
scheduler in this repo (see "No deployment infra" below).

## Known placeholders / still needs real data

- **ETL thresholds** (`app/decision/etl_thresholds.py`) — transcribed directly from the thesis's Table 2, real.
- **RSB GDD base temp** (15°C) — cited in the thesis's RSB literature review, real.
- **BPH GDD base temp**, **CRF window size**, **RH threshold for Humidity Persistence**, and the **WSI daily water requirement constant** — still placeholder values with no citation behind them yet. See `ml/config.py` and `app/preprocessing/features.py` for where these live.
- The training dataset itself is synthetic, not collected field data, and spans only 5 municipalities over 6 years — model performance (BPH R²≈0.35, RSB R²≈0.21; see `ml/weights/{pest}/bilstm_{pest}_test_metrics.json`) reflects that ceiling, not primarily model capacity (confirmed by testing a much smaller/more regularized architecture and getting an equivalent result). RSB currently fails `ml/validity_test.py`'s statistical-validity threshold (R² < 0.3) — the 14-vs-28-day CRF window ambiguity in `ml/config.py` was tested directly (28 days made it worse: R² 0.206 → 0.135), so 14 is the confirmed better choice, not just the convenient one; RSB's low R² looks like a genuine data ceiling from the synthetic dataset rather than a fixable hyperparameter.
- RSB's ResNet-50 classifier scores a perfect 1.0 accuracy on its held-out test set (`ml/weights/rsb/resnet50_rsb_test_metrics.json`), vs. BPH's 0.99 with a nonzero confusion matrix (`ml/weights/bph/resnet50_bph_test_metrics.json`). Checked `ml/resnet/prepare_dataset.py`'s split logic directly: it's hash-keyed on the *original source image filename*, so every crop from one annotated image always lands in the same train/val/test bucket — no near-duplicate leakage across the split. The perfect score is more likely explained by RSB's smaller test set (933 images vs. BPH's 1,508, per `ml/resnet/datasets/processed/{bph,rsb}/prepare_summary.json`) and rice stem borer damage symptoms (dead hearts/white ears) being more visually distinct from the other four tracked pests than BPH's planthopper-vs-planthopper-like-insect distinction.
- No deployment infrastructure exists (no Dockerfile for the API or either frontend, no CI). `docker-compose.yml` at the repo root only runs Postgres for local dev.

## Migration notes from the Node server

- `/api/health`, `/api/auth/login`, `/api/weather/forecast` all keep the same
  request/response shape as the old Express server so `admin-web`'s
  `src/lib/api.ts` needs minimal changes — just point `VITE_API_URL` at
  `http://localhost:8000` instead of `:5000`.
- `/api/auth/login` now also matches against `farmer_users.py` and returns
  `account_type: "lgu" | "farmer"` in the response, since the mobile app
  uses the same endpoint.
- `user-mobile` (React + Vite, migrated off Expo) is a live consumer of this
  API now too — see its own README for the mobile-specific setup. Its dev
  server runs over HTTPS on `:5173`+ (`@vitejs/plugin-basic-ssl`, needed for
  camera access), which is why `CORS_ORIGINS` in `.env.example` lists both
  `http://` and `https://` variants of `:5173`–`:5175`.
- Mongoose was installed in the old Node server but never actually wired to
  a database — there was nothing to port. Accounts and reports now live in
  Postgres (see "Database" above); `lgu_users.py`/`farmer_users.py` are
  Postgres-backed accessors, not hardcoded lists.
- Once `admin-web` and `user-mobile` are fully cut over, delete the old
  `server` workspace and remove it from the root `package.json` workspaces
  list.
