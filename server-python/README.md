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

## Run

```
npm run dev
```

Starts Uvicorn with auto-reload on `http://localhost:8000`. Interactive API
docs are auto-generated at `http://localhost:8000/docs`.

At startup, `app/main.py` loads the trained BiLSTM weights for both pests
(BPH and RSB) from `ml/weights/`. If a pest's weights aren't there yet (e.g.
a fresh clone before training has been run), that pest's forecast endpoints
report `status: "model_not_loaded"` instead of crashing the app — see
`ml/bilstm/train.py` below.

## Folder structure

```
server-python/
├── app/                       # the serving API — thin, no training code
│   ├── main.py                 # FastAPI app, CORS, router registration, startup model load
│   ├── config.py               # Settings loaded from .env (pydantic-settings)
│   ├── routers/
│   │   ├── auth.py             # POST /api/auth/login (LGU techs + farmers)
│   │   ├── weather.py          # GET /api/weather/forecast (Open-Meteo forward forecast)
│   │   └── inference.py        # see "API endpoints" below
│   ├── data/                    # Hardcoded accounts (swap for a real DB later)
│   │   ├── lgu_users.py          # also the coordinate lookup for live weather fetches
│   │   └── farmer_users.py
│   ├── schemas/                  # Pydantic request/response models
│   ├── models/
│   │   ├── resnet_model.py        # ResNet-50 wrapper — still a stub, no image dataset yet
│   │   └── bilstm_model.py        # BiLSTM wrapper — trained, loads real weights
│   ├── decision/
│   │   └── etl_thresholds.py      # fixed, non-learned Low/Medium/High bucketing (thesis Table 2)
│   ├── explain/                    # (reserved — SHAP lives in ml/explainability instead)
│   └── preprocessing/
│       └── features.py             # GDD/CRF/HP/VPD/WSI/trend — canonical formulas, shared
│                                    #   between training (ml/) and inference (app/)
│
├── ml/                          # training pipeline — separate from the serving app
│   ├── config.py                 # per-pest params (T_base, CRF window, RH threshold), paths
│   ├── datasets/
│   │   ├── raw/                   # gitignored — untouched weather_raw.csv / pest_raw.csv
│   │   ├── cleaning/
│   │   │   └── clean_timeseries.py # dedupe, fix sensor errors, interpolate gaps, merge
│   │   └── processed/              # gitignored — cleaned CSV + built sequences (.npz)
│   ├── bilstm/
│   │   ├── build_sequences.py      # cleaned CSV -> (X_sequence, X_static, y) per pest
│   │   └── train.py                # trains + evaluates (RMSE/MAE/R²), saves to ml/weights/
│   ├── resnet/                     # image classifier training — not started (no dataset)
│   ├── explainability/
│   │   └── shap_report.py          # SHAP GradientExplainer over the trained BiLSTM
│   └── weights/
│       ├── bph/                     # bilstm_bph.keras + scalers + test metrics
│       └── rsb/                     # bilstm_rsb.keras + scalers + test metrics
│
├── uploads/                    # Field images land here (gitignored)
├── requirements.txt
├── .env.example
└── package.json                # so `npm run dev -w server-python` works from root
```

## API endpoints

| Endpoint | What it does |
|---|---|
| `GET /api/health` | Liveness check |
| `POST /api/auth/login` | LGU tech + farmer accounts |
| `GET /api/weather/forecast` | Forward-looking weather (Open-Meteo), used by the dashboard's Climate Drivers charts |
| `POST /api/inference/image` | ResNet-50 image classification — stub, returns `model_not_loaded` |
| `POST /api/inference/forecast` | BiLSTM forecast from a caller-supplied 14-day weather window |
| `GET /api/inference/forecast/live` | Same, but fetches the real past 14 days for a municipality itself |
| `GET /api/inference/forecast/trajectory` | Up to 14 sequential daily forecasts (for charting a curve) — works from only past weather, since horizon ≥ days requested |
| `GET /api/inference/forecast/explain` | SHAP feature attributions for the same live prediction `/forecast/live` would return |

All forecast endpoints return a **continuous value** (hoppers/hill or %
damage) as the primary output, with the Low/Medium/High risk level as a
*derived* secondary field from `app/decision/etl_thresholds.py` — the model
predicts, ETL only buckets. See that module's docstring for why the split
matters.

## The ML pipeline, end to end

1. **Raw data** → `ml/datasets/raw/{weather,pest}_raw.csv` (synthetic, generated to spec — see thesis Sources of Data; not yet real PhilRice/PAGASA records).
2. **Clean**: `python -m ml.datasets.cleaning.clean_timeseries` → dedupes, fixes sensor errors, interpolates gaps, merges into `ml/datasets/processed/weather_pest_daily_clean.csv` + a `cleaning_report.json` you can cite directly.
3. **Build sequences**: `python -m ml.bilstm.build_sequences` → per-pest `.npz` files (14-day sequence features + static aggregate features + regression target), using per-pest parameters from `ml/config.py`.
4. **Train**: `python -m ml.bilstm.train --pest BPH` (and `--pest RSB`) → chronological 70/15/15 split with a purge gap (not random — sequences overlap, so a random split would leak), saves `.keras` weights + scalers + test metrics to `ml/weights/{pest}/`.
5. **Serve**: `app/main.py` loads those weights at startup; `app/models/bilstm_model.py` rebuilds the same features at inference time from live weather.
6. **Explain**: `ml/explainability/shap_report.py` — a `GradientExplainer` against a background sample from the pest's own training sequences, cached per pest after first use.

To retrain after changing feature engineering or getting new data, rerun
steps 2–4 in order — each stage's output feeds the next.

## Known placeholders / still needs real data

- **ETL thresholds** (`app/decision/etl_thresholds.py`) — transcribed directly from the thesis's Table 2, real.
- **RSB GDD base temp** (15°C) — cited in the thesis's RSB literature review, real.
- **BPH GDD base temp**, **CRF window size**, **RH threshold for Humidity Persistence**, and the **WSI daily water requirement constant** — still placeholder values with no citation behind them yet. See `ml/config.py` and `app/preprocessing/features.py` for where these live.
- The training dataset itself is synthetic, not collected field data — model performance (R² ≈ 0.2–0.4) reflects that, not primarily model capacity (confirmed by testing a much smaller/more regularized architecture and getting an equivalent ceiling).

## Migration notes from the Node server

- `/api/health`, `/api/auth/login`, `/api/weather/forecast` all keep the same
  request/response shape as the old Express server so `admin-web`'s
  `src/lib/api.ts` needs minimal changes — just point `VITE_API_URL` at
  `http://localhost:8000` instead of `:5000`.
- `/api/auth/login` now also matches against `farmer_users.py` and returns
  `account_type: "lgu" | "farmer"` in the response, since the mobile app
  will use the same endpoint.
- Mongoose was installed in the old Node server but never actually wired to
  a database — there's nothing to port there. `lgu_users.py`/`farmer_users.py`
  are still hardcoded lists; swapping in real persistence (Postgres via
  SQLAlchemy, or MongoDB via Motor/Beanie) is the next step before this
  goes to production.
- Once `admin-web` and `user-mobile` are fully cut over, delete the old
  `server` workspace and remove it from the root `package.json` workspaces
  list.

## Adding the ResNet-50 image model

Unlike BiLSTM, this one hasn't been started — there's no image dataset yet.
Once you have one:

1. Build the training pipeline under `ml/resnet/` (mirroring `ml/bilstm/`'s
   structure: a dataset loader, `train.py`, `evaluate.py`).
2. Save trained weights to `ml/weights/{bph,rsb}/resnet50_{pest}.keras`
   (paths already defined in `ml/config.py`'s `PEST_PARAMS`).
3. Implement `load()` and `predict()` in `app/models/resnet_model.py` —
   already defines the expected return shape (`ResnetPrediction`).
4. Call `.load()` for both pests at startup in `app/main.py`, following the
   same best-effort pattern already used for the BiLSTM models.
5. Uncomment `pillow` in `requirements.txt`.
