# Rice Pest System

Monorepo for a rice pest risk monitoring system: a FastAPI backend built for a
deep-learning inference pipeline, a React admin dashboard for LGU technicians,
an Expo mobile app for farmers, and a shared TypeScript types package.

```
pestwatcher-ph/
├── server-python/          # FastAPI API (Python) — auth, weather, ML inference
├── admin-web/              # Admin dashboard (React 19 + Vite)
├── user-mobile/            # Farmer app (Expo / React Native)
└── packages/shared-types/  # TypeScript interfaces shared by admin-web/user-mobile
```

See `structure.txt` for the fuller target layout, and
[`server-python/README.md`](server-python/README.md) for backend-specific
setup, folder structure, and where to drop in trained ML models.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 24.x | `node -v`. Anything 20+ should work; 24 is what this was built on. |
| npm | 11.x | Ships with Node 24. The repo uses **npm workspaces** — don't use yarn or pnpm. |
| Python | 3.11+ | `python --version`. Needed for `server-python`. |
| Git | any | |

For mobile work you also want the **Expo Go** app on your phone, or Android Studio /
Xcode if you plan to run an emulator.

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

### 4. Set up admin-web's env file

```bash
cp admin-web/.env.example admin-web/.env   # Windows: copy admin-web\.env.example admin-web\.env
```

This sets `VITE_API_URL` so the dashboard knows where the FastAPI server is
(`http://localhost:8000` by default — matches step 3). Without this file,
admin-web will fail to reach the API.

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
| Admin dashboard | `npm run dev --workspace=admin-web` | http://localhost:5173 |
| Mobile app | `npm start --workspace=user-mobile` | Expo dev server; scan the QR with Expo Go |

Uvicorn auto-reloads on save (`--reload` in the `dev` script). Vite hot-reloads.
Expo reloads on save.

`admin-web` needs the backend running to log in or load weather/dashboard
data — if you see "Failed to fetch", the FastAPI server (`server-python`) isn't
up.

Type-check / build without running:

```bash
npm run build --workspace=admin-web
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

**Expo can't resolve a module / Metro behaves oddly**
Metro and npm workspaces don't always agree about hoisting. Start with a clear cache:
`npm start --workspace=user-mobile -- --clear`.

**admin-web can't reach the API / requests go to the wrong URL**
`admin-web/.env` is missing. Copy it from `admin-web/.env.example` (see step 4
above) and restart the Vite dev server — Vite only reads `.env` at startup.

**Port 8000 already in use (Windows)**
`netstat -ano | findstr :8000`, then `taskkill /PID <pid> /F`. Or change `PORT` in
`server-python/.env`.

**A stopped `npm run dev` is still holding a port**
`npm run dev` spawns a child process (uvicorn/vite/tsx) that npm doesn't always
forward `Ctrl+C`/`SIGTERM` to. If a port is still bound after stopping a dev
server, find and kill the actual child process, not just the npm wrapper:
`netstat -ano | findstr :<port>`, then `taskkill /PID <pid> /F`.
