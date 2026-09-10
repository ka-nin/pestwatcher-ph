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

## Folder structure

```
server-python/
├── app/
│   ├── main.py            # FastAPI app, CORS, router registration
│   ├── config.py          # Settings loaded from .env (pydantic-settings)
│   ├── routers/
│   │   ├── auth.py        # POST /api/auth/login (LGU techs + farmers)
│   │   ├── weather.py     # GET /api/weather/forecast (Open-Meteo)
│   │   └── inference.py   # POST /api/inference/image, /api/inference/forecast
│   ├── data/               # Hardcoded accounts (swap for a real DB later)
│   │   ├── lgu_users.py
│   │   └── farmer_users.py
│   ├── schemas/            # Pydantic request/response models
│   ├── models/              # <- drop your trained ML models in here
│   │   ├── resnet_model.py  # ResNet-50 wrapper (image classification)
│   │   └── bilstm_model.py  # BiLSTM wrapper (outbreak timing forecast)
│   └── preprocessing/        # <- engineered biological features
│       └── features.py       # GDD, CRF, HP — ported from admin-web's JS
├── uploads/                # Field images land here (gitignored)
├── requirements.txt
├── .env.example
└── package.json            # so `npm run dev -w server-python` works from root
```

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

## Adding your models

1. Put trained weight files under `app/models/weights/` (create the folder;
   it's a natural place to `.gitignore` large binaries and pull them from
   cloud storage instead).
2. Implement `load()` and `predict()` in `resnet_model.py` / `bilstm_model.py`
   — both already define the expected return shapes
   (`ResnetPrediction`, `BiLstmPrediction`).
3. Call `.load()` once at startup (e.g. in `main.py`, guarded so dev reload
   doesn't reload weights on every file save) rather than per-request.
4. Uncomment `tensorflow`/`numpy`/`pillow` in `requirements.txt` once you're
   ready — they're commented out so the API scaffold stays lightweight to
   install until you actually need them.
