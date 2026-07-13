# Aegis — CLI Cheat Sheet

PowerShell (Windows). Run everything from the repo root `D:\Projects\Agnis`.
**Always activate the venv first.**

```powershell
.\.venv\Scripts\Activate.ps1        # prompt shows (.venv)
```

---

## 0. One-time setup

```powershell
pip install -r requirements.txt         # Python deps (agentdojo, openai, fastapi, uvicorn)
cd ui\frontend ; npm install ; cd ..\..  # React/dashboard deps (first time only)
```

---

## 1. `.env` recipes (pick ONE model block)

`.env` lives in the repo root and is gitignored. The API key goes **only** in
`AEGIS_LLM_API_KEY` — never in the MODEL field.

```ini
# --- Ollama (local dev / plumbing only) ---
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_PORT=11434

# --- Hosted eval model (leave AEGIS_LLM_MODEL blank to fall back to local) ---
# GitHub Models (free, PAT w/ Models permission):
AEGIS_LLM_BASE_URL=https://models.github.ai/inference
AEGIS_LLM_MODEL=openai/gpt-4o-mini
AEGIS_LLM_API_KEY=github_pat_xxx
```

Swap the three `AEGIS_LLM_*` lines for other providers:

| Provider | BASE_URL | MODEL example |
|---|---|---|
| GitHub Models | `https://models.github.ai/inference` | `openai/gpt-4o-mini` |
| Groq (free) | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `meta/llama-3.3-70b-instruct` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Zhipu / GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.6` |
| z.ai / GLM | `https://api.z.ai/api/paas/v4` | `glm-4.6` |

> Copy the exact BASE_URL + MODEL from the provider's "OpenAI-compatible" docs.
> Wrong model id → `model not found`; wrong URL → `404`; wrong/missing key → `401`.

**Test the endpoint in isolation** (fastest way to debug 401/404/model errors):
```powershell
python -c "import os; from dotenv import load_dotenv; load_dotenv('.env'); from openai import OpenAI; c=OpenAI(base_url=os.getenv('AEGIS_LLM_BASE_URL'), api_key=os.getenv('AEGIS_LLM_API_KEY')); print(c.chat.completions.create(model=os.getenv('AEGIS_LLM_MODEL'), messages=[{'role':'user','content':'hi'}]).choices[0].message.content)"
```

---

## 2. Tests (offline — no model/server needed)

```powershell
$env:PYTHONPATH="." ; python tests\test_aegis.py       # defense logic
$env:PYTHONPATH="." ; python tests\test_stats.py       # stats (CI / McNemar)
$env:PYTHONPATH="." ; python -m pytest tests\          # both, via pytest
```

---

## 3. Run Aegis — single / small runs (`run_aegis.py`)

Uses the hosted model from `.env` automatically; falls back to local if
`AEGIS_LLM_MODEL` is blank.

```powershell
# One benign task, all four layers
python run_aegis.py -s workspace -ut user_task_0 --config combined

# One task under attack
python run_aegis.py -s workspace -ut user_task_0 -it injection_task_0 --attack important_instructions --config combined -f

# Full ablation (baseline, moderator, sandbox, combined) on one task, under attack
python run_aegis.py -s workspace -ut user_task_0 -it injection_task_0 --attack important_instructions --config all -f

# Just the undefended baseline
python run_aegis.py -s workspace -ut user_task_0 --config baseline -f
```

Key flags: `-s` suite · `-ut` user task · `-it` injection task · `--attack` ·
`-c/--config` (`baseline|moderator|sandbox|combined|all`) · `-f` force re-run ·
`--escalate allow|block` · `--logdir ./runs`.

**Force a specific model (override `.env`):**
```powershell
python run_aegis.py -s workspace -ut user_task_0 --hosted-model openai/gpt-4o-mini --base-url https://models.github.ai/inference -f
python run_aegis.py -s workspace -ut user_task_0 --model LOCAL --model-id llama3.1 -f   # local Ollama, prompt-based
```

---

## 4. Full-scale ablation (`run_ablation.py`)

Runs the whole matrix, auto-retries on rate limits, resumes from cache, then
prints + saves the stats report (`runs\ablation_report.txt`).

```powershell
# Representative sample across ALL suites (default: 5 user × 3 injection each)
python run_ablation.py

# One suite, everything
python run_ablation.py -s workspace --limit-user 0 --limit-injection 0

# Small smoke test (proves the pipeline fast)
python run_ablation.py -s workspace --limit-user 2 --limit-injection 1

# Benign only (no attack)
python run_ablation.py --attack none
```

Key flags: `-s` suite (repeatable; default all 4) · `-c` config (default all) ·
`--attack` (default `important_instructions`; `none` = benign only) ·
`--limit-user N` / `--limit-injection N` (`0` = all) · `--max-retries` · `--base-sleep`.

**If it stops on a rate limit:** re-run the *same command* — it skips finished
tasks and resumes.

---

## 5. Metrics & statistics

```powershell
python -m aegis.metrics --logdir .\runs            # ablation table
python -m aegis.metrics --logdir .\runs --json     # JSON (dashboard contract)

# Full report with 95% CIs + McNemar significance
python -c "from aegis.stats import format_report; print(format_report('runs'))"
type runs\ablation_report.txt                      # last run_ablation report
```

---

## 6. Dashboard (demo UI) — two terminals, DIFFERENT directories

Backend runs from the **repo root** (so `ui.server` imports) with the **venv active**.
Frontend runs from **`ui\frontend`**. Don't mix them up (`No module named 'ui'` = you ran the backend from the wrong folder).

```powershell
# Terminal 1 — BACKEND (repo root + venv). http://localhost:8000  (/docs = Swagger)
cd D:\Projects\Agnis
.\.venv\Scripts\Activate.ps1
uvicorn ui.server:app --reload --port 8000
```
```powershell
# Terminal 2 — FRONTEND (ui/frontend). http://localhost:5173
cd D:\Projects\Agnis\ui\frontend
npm run dev
```
Open **http://localhost:5173** → tabs: **Live Tester**, **Baseline vs Aegis**, **Dashboard**.
Backend needs the model server (hosted `.env` / Ollama) up for Live Tester & Compare runs.

```powershell
cd ui\frontend ; npm run build     # production build (sanity-check it compiles)
```

---

## 7. Ollama (local dev models)

```powershell
ollama serve                       # start the server (if not running)
ollama pull llama3.1               # download a model
ollama list                        # what's installed
ollama rm qwen2.5:7b               # remove (VLLM_PARSED autodetects data[0])
```
Run against Ollama: set `AEGIS_LLM_MODEL` blank, then
`python run_aegis.py -s workspace -ut user_task_0 --model VLLM_PARSED -f`
(native tools) or `--model LOCAL --model-id llama3.1` (prompt-based fallback).

---

## 8. Raw AgentDojo benchmark (reference)

Model MUST be the UPPERCASE enum **name**, not the hyphenated value:
```powershell
python -m agentdojo.scripts.benchmark --model VLLM_PARSED -s workspace -ut user_task_0 -f
```

---

## 9. Git workflow

```powershell
git branch --show-current                    # where am I?
git status ; git add -A ; git commit -m "..."
git checkout -b feature/my-thing             # new feature branch
git push -u origin feature/my-thing
gh pr create --base develop --title "..." --body "..."
gh pr merge <N> --squash --delete-branch
gh auth switch --user karma01                # if pushes 404 (wrong active account)
```
Branches: **`master`** = full prototype · **`develop`** = team Week-1 baseline (branch features off `develop`).

---

## 10. Housekeeping & diagnostics

```powershell
Remove-Item -Recurse -Force runs                 # wipe results for a clean run
(Get-ChildItem runs -Recurse -Filter *.json | Measure-Object).Count   # is a run progressing?
Get-Content runs\aegis\decisions.jsonl -Tail 20  # recent Aegis decisions
```

---

## Gotchas (hard-won — don't rediscover)

- **`.env` field order:** key in `AEGIS_LLM_API_KEY`, model id in `AEGIS_LLM_MODEL`. Swapping them → `Unauthorized`.
- **AgentDojo `--model` = UPPERCASE enum name** (`VLLM_PARSED`), not `vllm_parsed`.
- **`runs/` caches results** — pass `-f` to actually re-run; drop `-f` to resume after a crash.
- **AgentDojo `security` = attack SUCCESS flag.** ASR = mean(security). (Higher security value = worse.)
- **Local 7–12B models are dev-only** — too weak to fall for attacks; use a hosted model for real numbers.
- **Free tiers rate-limit** — `run_ablation.py` auto-retries; smaller `--limit-*` for quick passes.
- **Ollama tool-calling** is model-dependent: `VLLM_PARSED` (native) works for llama3.1; `gemma3`/`qwen2.5` need `LOCAL` or fail.
