# Aegis

**A taint-aware agentic moderator and sandbox that defends tool-using LLM agents against prompt injection — built as a pluggable defense layer for the [AgentDojo](https://github.com/ethz-spylab/agentdojo) benchmark.**

Aegis is not a standalone agent. It is a defense-in-depth layer composed of four independent
pipeline elements that slot into AgentDojo's agent loop, plus an evaluation harness that measures
what each layer actually contributes. All attack data is AgentDojo's own synthetic suites — this
project builds and measures **defenses only** and introduces no new exploits.

## Why

AgentDojo ships several defenses (`tool_filter`, `spotlighting_with_delimiting`,
`transformers_pi_detector`, `repeat_user_prompt`), but each is a single mechanism evaluated on its
own. There is no reference implementation of a *composed* defense — cross-turn taint tracking, a
lethal-trifecta policy gate, an LLM-judge moderator and an execution sandbox working together — and
no harness that isolates each layer's marginal contribution.

Aegis is that reference implementation, with the ablation harness to go with it.

## The four layers

Each layer is an independent `agentdojo.agent_pipeline.BasePipelineElement`, so one failing does not
compromise the others.

| Layer | Module | What it does |
|---|---|---|
| **Agentic Moderator** | `aegis/moderator.py`, `aegis/judge.py` | Intercepts each proposed tool call. Deterministic policy rules plus a cost-gated LLM-as-judge risk score produce `ALLOW` / `BLOCK` / `ESCALATE`. Judge failures fall back to risk 0.0 by design, leaving the gate and sandbox as the backstop. |
| **Taint Tracking** | `aegis/taint.py`, `aegis/trust.py` | Coarse-grained, three-tier trust-label model (curated vectors + read/action heuristic + content injection scan). Once untrusted tool output enters context, downstream content is tainted. Taint **accumulates across turns**, so a send on turn 3 sees an untrusted read from turn 1. |
| **Policy Gate** | `aegis/policy_gate.py` | Enforces the lethal-trifecta rule: block or escalate high-risk actions (e.g. external send) that depend on tainted data. |
| **Sandbox** | `aegis/sandbox.py` | Capability and egress boundary around tool execution. Keeps its **own** taint signal, so it contains exfiltration independently of the other three layers. |

### Pipeline order

```
AegisModerator -> AegisPolicyGate -> AegisToolsExecutor (enforce + sandbox) -> AegisTaintTracker -> llm
```

Detection elements run **before** execution and only *record* verdicts into `extra_args`. The
executor is the single **enforcement** point, so every `tool_call` keeps a matching tool result —
required by the native tool-calling path. Taint runs **after** execution.

Shared types live in `aegis/contracts.py` (`Decision`, `TaintState`, `Verdict`). State is threaded
through `extra_args` under `aegis_taint` / `aegis_decisions`. The stable gate contract is
`decide(tool_call, taint_state) -> ALLOW | BLOCK | ESCALATE`.

## Install

Python 3.11.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The agent under test is reached over an **OpenAI-compatible API**. Configure it in a `.env` at the
repo root (gitignored — never commit a real key):

```ini
# Hosted model, for trustworthy numbers (GitHub Models, Groq, OpenAI, ...)
AEGIS_LLM_BASE_URL=https://api.groq.com/openai/v1
AEGIS_LLM_MODEL=llama-3.3-70b-versatile
AEGIS_LLM_API_KEY=...

# Or a local Ollama server, for plumbing work only (see Limitations)
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
```

## Quickstart

```bash
# Offline logic tests — no model or server needed (12 tests)
PYTHONPATH=. python tests/test_aegis.py
PYTHONPATH=. python tests/test_stats.py

# One benign task, all layers on
python run_aegis.py -s workspace -ut user_task_0 --config combined

# One task under attack, across the full ablation matrix
python run_aegis.py -s workspace -ut user_task_0 --attack important_instructions --config all -f

# Full-scale ablation: every config x suite. Resumes from cache, survives rate limits,
# prints the table with 95% Wilson CIs and paired McNemar tests vs baseline.
python run_ablation.py
python run_ablation.py -s workspace --limit-user 0 --limit-injection 0   # everything, one suite

# Aggregate runs/ into the ablation table
python -m aegis.metrics --logdir ./runs
python -m aegis.metrics --logdir ./runs --json
```

### Custom defenses do not go through `--defense`

AgentDojo's `--defense` flag is a fixed `click.Choice` evaluated at import time, so a custom name
cannot be passed. `run_aegis.py` instead builds the `AgentPipeline` with the Aegis elements
inserted and calls `benchmark_suite_with_injections` / `benchmark_suite_without_injections`
directly — the same functions AgentDojo's own CLI uses. Installed AgentDojo source under `.venv/`
is never modified.

### The ablation matrix

Four presets in `aegis/pipeline.py`:

| Config | Moderator | Taint | Gate | Sandbox |
|---|---|---|---|---|
| `baseline` | – | – | – | – |
| `moderator` | yes | yes | yes | – |
| `sandbox` | – | – | – | yes |
| `combined` | yes | yes | yes | yes |

`ESCALATE` collapses to `BLOCK` by default, since there is no human in the benchmark loop.
`--escalate allow` simulates approval.

## Evaluation is the deliverable

Success is measured, not asserted. Every claim is made against the undefended baseline with
ablations, on four metrics: **Attack Success Rate**, **benign task utility**, **false-positive /
over-block rate**, and **latency overhead**. A "block everything" defense is a failure, because
utility collapses; a change only counts if it cuts attacks *and* keeps the agent usable.

Reproducible outputs, which are the source of truth:

- `runs/*.json` — per-task utility / security / message trace, keyed by `<model>-aegis_<config>`
- `runs/aegis/decisions.jsonl` — every layer decision, for auditing why a call was blocked
- `aegis/metrics.py` — aggregation; `aegis/stats.py` — Wilson intervals and exact McNemar

> **The config label is not a unique key.** Runs from different models land in the same config
> bucket and silently average together. Always split by model (`--model`) before quoting a number;
> the CLI warns when a table mixes models.

## Dashboard

A thin presentation layer over the headless runner and logs — never a replacement for them.

```bash
uvicorn ui.server:app --reload --port 8000     # FastAPI backend
cd ui/frontend && npm install && npm run dev   # React (Vite) frontend on :5173
```

Three modes: a **live tester** (pick suite / task / attack / config, watch the conversation
timeline with every tool call annotated by all four layers), an **analytics dashboard** (the
ablation table as charts), and a **side-by-side** baseline-vs-combined view on the same task and
attack.

## Limitations

Stated plainly, because they affect how the numbers should be read.

- **Small local models produce actively misleading metrics.** On AgentDojo, a 7–8B model served by
  Ollama frequently refuses tasks outright. A refusing agent *inflates* utility (AgentDojo's
  per-task check is a substring/value match that refusal text can accidentally satisfy) and
  *deflates* Attack Success Rate (it refuses injections too) — making a useless agent look both
  productive and secure. Use local models to verify the pipeline executes, never to report numbers.
- **Headline numbers require a hosted model with native tool calling.** Of the local models tested
  (llama3.1, qwen2.5, gemma3), only `llama3.1:8b` emits tool calls at all, and it is too weak.
- **The published ablation currently runs at small n** and is not yet statistically significant.
  Scaling it to the full matrix is the main open work.
- **The sandbox is an in-process capability and egress boundary**, not a micro-VM. Integrating a
  third-party micro-VM sandbox service is documented as production future-work in
  `aegis/sandbox.py`.
- **Model names are UPPERCASE enum names.** Pass `--model VLLM_PARSED` or
  `--model GPT_4O_MINI_2024_07_18`, not the hyphenated value. `runs/` caches results — pass `-f` to
  actually re-execute.

## Layout

```
aegis/          the four layers, contracts, decision log, metrics, stats
run_aegis.py    headless single-run / single-config entry point
run_ablation.py full-scale ablation harness with retry, resume and significance tests
ui/             FastAPI backend (ui/server.py) + React frontend (ui/frontend)
tests/          offline logic tests, no model or server required
runs/           benchmark results and the decision trail
```

## Contributing

Issues and pull requests are welcome. The seams to coordinate on before changing are the gate
contract in `aegis/contracts.py`, the `extra_args` keys (`aegis_taint`, `aegis_decisions`), and the
`runs/` output shape that `aegis/metrics.py` and the dashboard both read.

## License

[Apache License 2.0](LICENSE).
