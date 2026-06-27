# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Aegis** is a taint-aware agentic moderator and sandbox framework that defends tool-using LLM agents against prompt injection. It is a defense-in-depth layer plugged into the **AgentDojo** benchmark — not a standalone agent. The full motivation, goals, success criteria, scope, and team responsibilities live in [Aegis_Project_Context.md](Aegis_Project_Context.md); read it before making architectural decisions.

**Current state:** core implemented. The `aegis/` package implements all four layers as AgentDojo pipeline elements, with `run_aegis.py` as the entry point and offline logic tests in `tests/` (8 passing). Dependencies are in `requirements.txt` (`agentdojo==0.1.35`, `openai==2.43.0`).

Layer bodies are implemented (not stubs): moderator with deterministic rules + cost-gated LLM-judge (`aegis/judge.py`, safe fallback to risk 0.0); coarse taint via a 3-tier trust-label model (`aegis/trust.py` — curated vectors + read/action heuristic + content injection scan); lethal-trifecta policy gate; and a capability/egress sandbox (`aegis/sandbox.py`) that keeps its own taint signal so it contains exfiltration independently of the other layers. Remaining intentional non-stub: a third-party micro-VM is documented as production future-work (see sandbox.py). The demo UI (FastAPI + React) is designed but not yet built. No git repo yet.

## Environment & commands

Python 3.11 in a local venv at `.venv`. This is a Windows machine; the shell is PowerShell.

```powershell
# Activate the venv (PowerShell)
.\.venv\Scripts\Activate.ps1

# Run the AgentDojo benchmark (the core eval loop)
python -m agentdojo.scripts.benchmark --suite workspace --defense tool_filter

# Baseline (no defense), single suite, custom log dir
python -m agentdojo.scripts.benchmark -s banking --logdir ./runs

# Run one user task with an attack, loading a custom Aegis module
python -m agentdojo.scripts.benchmark -s slack -ut user_task_0 --attack important_instructions \
  --defense <aegis_defense_name> --module-to-load aegis.defenses
```

Key CLI flags (from `agentdojo.scripts.benchmark`): `--model` / `--model-id` (use `--model-id` for local Ollama-style models), `--suite/-s`, `--defense`, `--attack`, `--user-task/-ut`, `--injection-task/-it`, `--logdir` (default `./runs`), `--max-workers`, `--force-rerun/-f`, and **`--module-to-load/-ml`** — the hook for registering custom Aegis defenses, attacks, and suites without forking AgentDojo.

The reasoning LLM is reached via an **OpenAI-compatible API** (`openai` SDK): local Ollama for development, a stronger hosted model for final evaluation. Configure via the standard `OPENAI_API_KEY` / `OPENAI_BASE_URL` environment variables; do not hardcode endpoints.

## Local model dev setup (Ollama)

A `.env` (auto-loaded by AgentDojo from the repo root) holds the Ollama wiring: `OPENAI_API_KEY=ollama`, `OPENAI_BASE_URL=http://localhost:11434/v1`, `LOCAL_LLM_PORT=11434`. With that in place:

```powershell
ollama pull llama3.1
ollama rm qwen2.5:7b   # VLLM_PARSED autodetects data[0] from /v1/models; keep only the model you want
python -m agentdojo.scripts.benchmark --model VLLM_PARSED -s workspace -ut user_task_0 -f
```

**Recommended dev combo: `VLLM_PARSED` + llama3.1.** It actually emits native tool calls, so the Aegis pipeline elements have a live tool-call stream to intercept. (Observed: `LOCAL` + llama3.1 *refuses* every task and emits no `<function=...>` call — useless for exercising the layers. qwen2.5 fails both paths. See the per-combo table in conversation history if revisiting.)

**Hard-won gotchas (these cost real time — don't rediscover them):**

- **Model name must be the UPPERCASE enum *name*, not the hyphenated value.** Installed Click (8.4.1) added native Enum support to `click.Choice`, so it matches `ModelsEnum` *member names*: pass `--model LOCAL` / `VLLM_PARSED` / `GPT_4O_MINI_2024_07_18`, **not** `local` / `gpt-4o-mini-...`. AgentDojo 0.1.35's own documented lowercase default (`gpt-4o-2024-05-13`) is broken under this Click version.
- **Two local providers, different tool-calling mechanisms:**
  - `--model LOCAL` → `LocalLLM`: prompt-based. Injects tool schemas as text and parses `<function=name>{json}</function>` out of the reply. **Respects `--model-id`** (deterministic model choice). Format is Llama-style — use a **Llama** model here; qwen2.5 ignores the format and answers conversationally.
  - `--model VLLM_PARSED` → `OpenAILLM`: relies on the server returning **native** `tool_calls`. **Ignores `--model-id`** — autodetects `data[0]` from `/v1/models`, so with multiple models pulled, *which one runs is non-deterministic*. Ollama surfaces native tool_calls for some models (llama3.1) but returned empty for qwen2.5.
- **`runs/` caches results.** A re-run prints "Skipping … already run" and reports the *stale* number. Pass `-f`/`--force-rerun` to actually execute.
- **Local models are for plumbing, not numbers.** 7–8B models served by Ollama score near the floor on AgentDojo (weak multi-step tool use: null args, hallucinated tool outputs, refusals, giving up early). AgentDojo's local adapters were built for large vLLM-hosted models. Use Ollama to verify the pipeline executes and to develop/test the Aegis layers against a live tool-call stream — **but headline ASR / utility / ablation numbers must come from a strong API model.**
- **The utility metric reports FALSE POSITIVES on a non-functional agent.** Observed: llama3.1 refused a task with zero tool calls and still scored `utility=True`, because AgentDojo's per-task check is a substring/value match the refusal text accidentally satisfied. A refusing agent simultaneously *inflates* utility (spurious matches) and *deflates* Attack Success Rate (it refuses injections too) — making a useless agent look both productive and secure. This is why local numbers don't just run low, they actively mislead; never report baselines/ablations from a local model, and state this as a limitation in the report.

## How Aegis integrates with AgentDojo

This is the big-picture fact that the rest of the design depends on. AgentDojo composes an agent as a sequence of **pipeline elements**, each subclassing `agentdojo.agent_pipeline.BasePipelineElement` and implementing a single method:

```python
def query(self, query, runtime, env, messages, extra_args)
    -> (query, runtime, env, messages, extra_args)
```

Elements are threaded together — notably inside a `ToolsExecutionLoop` (see `agent_pipeline/agent_pipeline.py`, `PipelineConfig`, and the built-in defenses: `tool_filter`, `transformers_pi_detector`, `repeat_user_prompt`, `spotlighting_with_delimiting`). **Aegis's four layers are implemented as custom `BasePipelineElement`s inserted into this loop**, then registered and selected via `--defense <name> --module-to-load <module>`. The loop is the seam; do not modify installed AgentDojo source under `.venv/`.

The four layers (each an independent element, so one failing does not compromise the others):

1. **Agentic Moderator** — intercepts each proposed tool call; deterministic policy rules + a lightweight LLM-as-judge risk score → `ALLOW / BLOCK / ESCALATE`.
2. **Taint Tracking (coarse-grained)** — labels data trusted/untrusted; once any untrusted tool output enters context, downstream content is tainted. Taint state is carried through the pipeline (via `extra_args` / env).
3. **Policy Gate** — enforces the lethal-trifecta rule: block/escalate high-risk actions (e.g. external send) that depend on tainted data.
4. **Sandbox** — runs tool execution in isolation so an injection slipping past the moderator still cannot reach the host or leak data. Uses a third-party micro-VM-style sandbox service, not built from scratch.

**Stable interface contracts (keep these stable across the team's modules):**
- taint tracker → policy gate: `decide(tool_call, taint_state) -> ALLOW | BLOCK | ESCALATE` (implemented in `aegis/policy_gate.py`).
- everything → logging: every decision is logged so benchmark numbers are reproducible (`aegis/decision_log.py` → `runs/aegis/decisions.jsonl`).
- shared types live in `aegis/contracts.py` (`Decision`, `TaintState`, `Verdict`); Aegis state is threaded through `extra_args` under `aegis_taint` / `aegis_decisions`.

## The Aegis package & how to run it

**Custom defenses do NOT go through `--defense`.** That flag is a fixed `click.Choice(DEFENSES)` evaluated at import time, so a custom name can't be passed. Instead, `run_aegis.py` builds an `AgentPipeline` with the Aegis elements inserted and calls AgentDojo's `benchmark_suite_with_injections` / `benchmark_suite_without_injections` directly (the same functions AgentDojo's own CLI wrapper uses). `--module-to-load` remains only for custom *attacks/suites* (which have registries).

`aegis/pipeline.py` rebuilds the `ToolsExecutionLoop` in this order:

```
AegisModerator → AegisPolicyGate → AegisToolsExecutor(enforce + sandbox) → AegisTaintTracker → llm
```

Detection elements run **before** execution and only *record* verdicts into `extra_args`; the executor is the single **enforcement** point (so every `tool_call` keeps a matching tool result — required for the OpenAI/`VLLM_PARSED` native-tool path). Taint runs **after** execution and **accumulates across turns**, so a "send" on turn 3 sees taint from an untrusted read on turn 1.

Run it (model is the UPPERCASE enum name, same gotcha as the CLI):

```powershell
# One benign task, all layers
python run_aegis.py -s workspace -ut user_task_0 --config combined

# Full ablation under attack: baseline, moderator, sandbox, combined
python run_aegis.py -s workspace --attack important_instructions --config all -f

# Offline logic tests (no model/server needed)
$env:PYTHONPATH="."; python tests/test_aegis.py
```

The four `--config` presets in `aegis/pipeline.py` (`PRESETS`) are the ablation matrix: `baseline` (undefended), `moderator` (detection stack, no sandbox), `sandbox` (isolation only), `combined`. `ESCALATE` collapses to BLOCK by default (no human in the benchmark loop); `--escalate allow` simulates approval.

## Demo UI / dashboard (planned design)

A lightweight web UI (Prashanna's deliverable; Week 3–4) with two modes:

- **Live tester / demo** — pick suite / user task / attack / ablation config, run it, and watch the conversation timeline with each tool call annotated by all four layers (taint badge, moderator risk + verdict, gate verdict, enforcement: executed / blocked). Includes a trust-map panel.
- **Analytics dashboard** — ASR, benign utility, false-positive/over-block rate, and latency **across the four ablation configs** (the success-criteria table, rendered as charts).
- **Killer demo view** — baseline-vs-combined side-by-side on the same task+attack: the attack succeeds undefended on the left and is blocked by Aegis on the right.

**Architecture principle:** the UI is a **thin presentation layer over the headless CLI and logs**, never a replacement. `run_aegis.py` + `runs/*.json` (per-task utility/security/messages) + `runs/aegis/decisions.jsonl` (decision trail) remain the source of truth for reproducible numbers; the UI reads those and may trigger runs in-process. Headline numbers must still come from headless runs.

**Stack (decided): FastAPI + React.** A FastAPI backend exposes a thin API over the headless runner — trigger a run (wraps `run_aegis` logic), read aggregated results from `runs/*.json`, and stream `runs/aegis/decisions.jsonl`; a React frontend renders the two modes and the side-by-side view. More polished than a Streamlit app, at the cost of a separate frontend — so it is **sequenced after** the core layers and a first real evaluation run are complete. Keep the backend a thin wrapper: the headless CLI + logs remain the source of truth for reproducible numbers.

## Evaluation is the deliverable

Success is measured, not asserted. Always evaluate against an **undefended baseline** with **ablations** — four configs: baseline, moderator-only, sandbox-only, combined — to isolate each layer's contribution. Metrics: Attack Success Rate, benign task utility, false-positive/over-block rate, latency overhead. A "block everything" defense is a failure because utility collapses; a change only counts if it cuts attacks *and* keeps the agent usable. Log every run to `./runs` so results regenerate.

AgentDojo provides 4 suites — `workspace`, `banking`, `travel`, `slack` — with synthetic tasks and synthetic injection cases. All data is synthetic; this project builds and measures **defenses only** and introduces no new exploits.

`aegis/metrics.py` aggregates the per-task result JSONs under `runs/` into the ablation table (benign utility, utility-under-attack, ASR, latency + overhead, and utility-drop as the over-block proxy), keyed by config. It reads only `runs/*.json` (reproducible) and is the data contract the dashboard consumes:

```powershell
python -m aegis.metrics --logdir ./runs            # printed table
python -m aegis.metrics --logdir ./runs --json     # JSON for the UI
```

## Module ownership (coordinate before changing shared seams)

- **Pawan** — Detection: moderator, coarse taint tracking, trust-label model.
- **Asmita** — Containment: sandbox integration, lethal-trifecta policy gate, human-escalation path.
- **Prashanna** — Evaluation: AgentDojo harness wiring, metrics & logging, ablations, dashboard.
