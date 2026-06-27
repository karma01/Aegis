# Aegis Demo UI

A thin presentation layer over the headless runner + logs (see the project root
`CLAUDE.md`). FastAPI backend in `ui/server.py`, React (Vite) frontend in
`ui/frontend/`.

## Run (two terminals, from the repo root)

**1. Backend** (serves metrics/decisions from `runs/`, and `POST /api/run`):

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn ui.server:app --reload --port 8000
```

**2. Frontend** (Vite dev server, proxies `/api` → `:8000`):

```powershell
cd ui/frontend
npm install        # first time only
npm run dev        # http://localhost:5173
```

Open http://localhost:5173.

## Modes

- **Live Tester** — pick suite / task / defense config / attack, run it, and watch
  the tool calls flow through the four Aegis layers with per-call verdicts and the
  conversation timeline (blocked calls flagged). *Requires the model server
  (Ollama / API) to be running.*
- **Dashboard** — the ablation table (benign utility, ASR, latency overhead,
  over-block) aggregated from `runs/`. Works without a model; populate it by
  running `python run_aegis.py ... --config all`.

## Endpoints

`GET /api/options` · `GET /api/suite/{suite}` · `GET /api/metrics` ·
`GET /api/decisions` · `POST /api/run` · `GET /api/health`
