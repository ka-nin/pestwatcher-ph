# Rice Pest System

Monorepo for a rice pest risk monitoring system: an Express + MongoDB API, a React admin
dashboard, an Expo mobile app for farmers, and a shared TypeScript types package.

```
rice-pest-system/
├── server/                 # Express API (TypeScript, Mongoose)
├── admin-web/              # Admin dashboard (React 19 + Vite)
├── user-mobile/            # Farmer app (Expo / React Native)
└── packages/shared-types/  # TypeScript interfaces shared by all three
```

See `structure.txt` for the fuller target layout.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 24.x | `node -v`. Anything 20+ should work; 24 is what this was built on. |
| npm | 11.x | Ships with Node 24. The repo uses **npm workspaces** — don't use yarn or pnpm. |
| MongoDB | 7.x+ | *Not needed yet* — see step 3. A local install, or a free Atlas cluster. |
| Git | any | |

For mobile work you also want the **Expo Go** app on your phone, or Android Studio /
Xcode if you plan to run an emulator.

## Setup after cloning

### 1. Clone and install

```bash
git clone https://github.com/ka-nin/rice-pest-system.git
cd rice-pest-system
npm install
```

Run `npm install` **from the repository root**, not from inside `server/` or `admin-web/`.
This is a workspace repo: the root install resolves dependencies for every workspace at
once and — importantly — creates the symlink

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

You can skip this if you're only touching the server, but `admin-web` won't build without it.

### 3. Create the server environment file

Create `server/.env`:

```bash
PORT=5000
```

`app.ts` loads this via `import 'dotenv/config'`, so changing `PORT` here changes the
port the server binds to. The file is gitignored — **never commit it.**

`MONGODB_URI` is not read yet. Mongoose is installed but the server has no connection
code, so you do **not** need MongoDB running to work on the project today. Once the
database is wired up, add:

```bash
MONGODB_URI=mongodb://127.0.0.1:27017/rice-pest-system
```

If you use Atlas instead of a local install, put its connection string there.

### 4. Verify

```bash
npm run dev --workspace=server
```

Then in another terminal:

```bash
curl http://localhost:5000/api/health
# {"status":"Server is running smoothly"}
```

## Running each app

All commands run from the repository root.

| What | Command | Where it runs |
|---|---|---|
| API server | `npm run dev --workspace=server` | http://localhost:5000 |
| Admin dashboard | `npm run dev --workspace=admin-web` | http://localhost:5173 |
| Mobile app | `npm start --workspace=user-mobile` | Expo dev server; scan the QR with Expo Go |

The server uses `tsx watch`, so it restarts on save. Vite hot-reloads. Expo reloads on save.

Type-check without emitting:

```bash
npx tsc --noEmit --project server
npm run build --workspace=admin-web
```

## Shared types

`packages/shared-types` is consumed as `@rice-pest/shared-types`. It has no build step —
its `main` and `types` both point at `src/index.ts`, and `tsx` and Vite compile it on the
fly. Edit the file and the consumers pick it up immediately; there's nothing to rebuild.

One caveat for later: because the entry point is raw TypeScript, a production `tsc` build
of the server would emit `require('@rice-pest/shared-types')` pointing at a `.ts` file that
plain Node cannot load. Before deploying, give the package a real build step that emits
`dist/index.js` + `dist/index.d.ts` and repoint `main`/`types` at those.

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

**Port 5000 already in use (Windows)**
`netstat -ano | findstr :5000`, then `taskkill /PID <pid> /F`. Or change `PORT` in
`server/.env`.
