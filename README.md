# Rice Pest System

Monorepo for a rice pest risk monitoring system: a FastAPI backend serving a
trained BiLSTM outbreak-forecasting model (live weather in, 14-day BPH/RSB
risk forecasts out) plus a ResNet-50 image classifier stub, a React admin
dashboard for LGU technicians wired end-to-end to that live pipeline, a React
+ Vite mobile-shell web app for farmers (also wired end-to-end, minus the
still-unimplemented image classifier), and a shared TypeScript types package.

```
pestwatcher-ph/
├── server-python/          # FastAPI API (Python) — auth, weather, ML inference
├── admin-web/              # Admin dashboard (React 19 + Vite)
├── user-mobile/            # Farmer app (React 19 + Vite, mobile-shell web app)
└── packages/shared-types/  # TypeScript interfaces shared by admin-web/user-mobile
```

See `structure.txt` for the fuller target layout, and
[`server-python/README.md`](server-python/README.md) for backend-specific
setup, the full folder structure, the ML training pipeline, and API
endpoints.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 24.x | `node -v`. Anything 20+ should work; 24 is what this was built on. |
| npm | 11.x | Ships with Node 24. The repo uses **npm workspaces** — don't use yarn or pnpm. |
| Python | 3.11+ | `python --version`. Needed for `server-python`. |
| Docker | any recent | Runs the PostgreSQL database `server-python` connects to — see step 3.5 below. |
| Git | any | |

`user-mobile` is a browser-based (Vite) app, not a native build — no Expo/Android
Studio/Xcode needed. To test its camera-based AI Pest Scan screen on a real
phone, you just need the phone and your computer on the same Wi-Fi network
(see [`user-mobile/README.md`](user-mobile/README.md#6-camera-testing-on-a-real-phone)).

## Setup after cloning

### 1. Clone and install JS workspaces

```bash
git clone https://github.com/ka-nin/pestwatcher-ph.git
cd pestwatcher-ph
npm install
```

Run `npm install` **from the repository root**, not from inside `admin-web/` or
`user-mobile/`. This is a workspace repo: the root install resolves dependencies
for every JS workspace at once and — importantly — creates the symlink

```
node_modules/@rice-pest/shared-types -> packages/shared-types
```

That symlink is the only reason `import { PestRecord } from '@rice-pest/shared-types'`
resolves. If you install inside a subfolder instead, that import will fail with
`Cannot find module '@rice-pest/shared-types'`.

### 2. Approve the esbuild install script

npm 11 blocks postinstall scripts by default. Vite needs esbuild's:

```bash
npm install-scripts approve esbuild
```

You can skip this if you're only touching the backend, but `admin-web` won't build without it.

### 3. Set up the Python backend

On Windows:

```bash
cd server-python
npm run setup   # creates .venv and installs requirements.txt
copy .env.example .env
cd ..
```

On macOS/Linux, `npm run setup` doesn't create the venv for you — do it manually:

```bash
cd server-python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd ..
```

See [`server-python/README.md`](server-python/README.md) for what's in `.env`
and the full folder breakdown (routers, ML model stubs, feature engineering).

### 3.5. Start the database

`server-python` stores LGU/farmer/SuperAdmin accounts and farmer-submitted
reports in PostgreSQL — start it with Docker Compose from the repo root:

```bash
docker compose up -d
```

`server-python/.env.example`'s `DATABASE_URL` already points at this
container's default credentials, so no further config is needed for local
dev. The backend creates its tables and seeds the same demo accounts
documented in `credentials.txt` automatically on first startup — see
[`server-python/README.md`](server-python/README.md) for the schema.

### 4. Set up admin-web's and user-mobile's env files

```bash
cp admin-web/.env.example admin-web/.env     # Windows: copy admin-web\.env.example admin-web\.env
cp user-mobile/.env.example user-mobile/.env # Windows: copy user-mobile\.env.example user-mobile\.env
```

Both set `VITE_API_URL` so the app knows where the FastAPI server is
(`http://localhost:8000` by default — matches step 3). Without these files,
each app falls back to `http://localhost:8000` anyway, but copying them
explicitly is what you'd change if pointing at a non-default backend URL.

### 5. Verify

```bash
npm run dev --workspace=server-python
```

Then in another terminal:

```bash
curl http://localhost:8000/api/health
# {"status":"Server is running smoothly"}
```

Interactive API docs are auto-generated at `http://localhost:8000/docs`.

## Running each app

All commands run from the repository root.

| What | Command | Where it runs |
|---|---|---|
| API server | `npm run dev --workspace=server-python` | http://localhost:8000 |
| Admin dashboard | `npm run dev --workspace=admin-web` | http://localhost:5173 (plain HTTP) |
| Mobile app | `npm run dev --workspace=user-mobile` | https://localhost:5173 (self-signed HTTPS, needed for camera access) |

Both `admin-web` and `user-mobile` default to Vite's port 5173 — if you run
them at the same time, Vite auto-bumps the second one to 5174/5175, which
the backend's default `CORS_ORIGINS` already covers (see
`server-python/.env.example`).

Uvicorn auto-reloads on save (`--reload` in the `dev` script). Vite hot-reloads
both frontends.

Both frontends need the backend running to log in or load weather/dashboard
data — if you see "Failed to fetch", the FastAPI server (`server-python`) isn't
up.

Type-check / build without running:

```bash
npm run build --workspace=admin-web
npm run build --workspace=user-mobile
```

## Shared types

`packages/shared-types` is consumed as `@rice-pest/shared-types`. It has no build step —
its `main` and `types` both point at `src/index.ts`, and Vite compiles it on the
fly. Edit the file and consumers pick it up immediately; there's nothing to rebuild.

It's currently consumed only by `admin-web` and isn't used by `server-python`
(Python and TypeScript don't share a type system) — if you want the two to stay
in sync, keep the Pydantic schemas in `server-python/app/schemas/` and the
TypeScript interfaces in `admin-web/src/lib/api.ts` updated together by hand.

## Troubleshooting

**`Cannot find module '@rice-pest/shared-types'`**
You installed from a subdirectory, or the install didn't finish. Run `npm install` from the
repository root and confirm `node_modules/@rice-pest/shared-types` exists as a symlink.

**VS Code still shows import errors after a successful install**
The TypeScript language server cached the old state. Run *TypeScript: Restart TS Server*
from the command palette, or reload the window.

**`EPERM: operation not permitted, unlink ...` on Windows during install**
A dev server or editor is holding a `.node` binary open. Stop every running dev server,
close the editor, delete the offending `node_modules`, and reinstall.

**user-mobile shows a blank white page / "Incompatible React versions" in the console**
`react` and `react-dom` drifted to different versions in `node_modules` (can happen
after installing from inside a workspace subfolder instead of the root, or a partial
install). Run `npm install` from the repository root; if it persists, delete
`node_modules/.vite` and `user-mobile/node_modules/.vite` to force Vite to
re-bundle dependencies, then restart `npm run dev`.

**admin-web or user-mobile can't reach the API / requests go to the wrong URL**
The app's `.env` is missing. Copy it from `.env.example` in that workspace (see step 4
above) and restart the Vite dev server — Vite only reads `.env` at startup.

**Port 8000 already in use (Windows)**
`netstat -ano | findstr :8000`, then `taskkill /PID <pid> /F`. Or change `PORT` in
`server-python/.env`.

**A stopped `npm run dev` is still holding a port**
`npm run dev` spawns a child process (uvicorn/vite/tsx) that npm doesn't always
forward `Ctrl+C`/`SIGTERM` to. If a port is still bound after stopping a dev
server, find and kill the actual child process, not just the npm wrapper:
`netstat -ano | findstr :<port>`, then `taskkill /PID <pid> /F`.
