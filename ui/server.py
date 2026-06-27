"""FastAPI backend for the Aegis demo UI.

Thin presentation layer: read-only endpoints serve aggregated metrics and the
decision log from ``runs/`` (work without a model); ``POST /api/run`` executes a
single task through an Aegis pipeline (needs the model server up).

Run from the repo root:
    uvicorn ui.server:app --reload --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentdojo.attacks.attack_registry import ATTACKS
from agentdojo.models import ModelsEnum
from agentdojo.task_suite.load_suites import get_suite

from aegis.decision_log import DEFAULT_LOG_PATH
from aegis.metrics import compute, to_dict
from aegis.pipeline import PRESETS
from ui.runner import run_single

SUITES = ["workspace", "banking", "travel", "slack"]
BENCHMARK_VERSION = "v1.2.2"

app = FastAPI(title="Aegis Demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; the React dev server runs on a different port
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    suite: str
    user_task: str
    config: str = "combined"
    model: str = "VLLM_PARSED"
    model_id: str | None = None
    attack: str | None = None
    injection_task: str | None = None
    escalate: str = "block"


class CompareRequest(BaseModel):
    suite: str
    user_task: str
    model: str = "VLLM_PARSED"
    model_id: str | None = None
    attack: str = "ignore_previous"  # the demo is about an attack
    injection_task: str | None = None
    escalate: str = "block"
    left_config: str = "baseline"
    right_config: str = "combined"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/options")
def options() -> dict:
    """Everything the control panel needs to populate its dropdowns."""
    return {
        "suites": SUITES,
        "configs": list(PRESETS),
        "attacks": list(ATTACKS),
        "models": [m.name for m in ModelsEnum],
        "escalate": ["block", "allow"],
    }


@app.get("/api/suite/{suite}")
def suite_tasks(suite: str) -> dict:
    if suite not in SUITES:
        raise HTTPException(404, f"unknown suite '{suite}'")
    s = get_suite(BENCHMARK_VERSION, suite)
    return {
        "suite": suite,
        "user_tasks": sorted(s.user_tasks.keys()),
        "injection_tasks": sorted(s.injection_tasks.keys()),
    }


@app.get("/api/metrics")
def metrics(logdir: str = "runs", baseline: str | None = None) -> dict:
    by_config, base = compute(logdir, baseline)
    return {"baseline": base, "configs": to_dict(by_config)}


@app.get("/api/decisions")
def decisions(limit: int = 200, logfile: str = DEFAULT_LOG_PATH) -> dict:
    path = Path(logfile)
    if not path.exists():
        return {"decisions": [], "total": 0}
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return {"decisions": records[-limit:], "total": len(records)}


@app.post("/api/run")
def run(req: RunRequest) -> dict:
    try:
        return run_single(
            suite=req.suite,
            user_task=req.user_task,
            config=req.config,
            model=req.model,
            model_id=req.model_id,
            attack=req.attack,
            injection_task=req.injection_task,
            escalate=req.escalate,
            benchmark_version=BENCHMARK_VERSION,
        )
    except Exception as exc:  # surface a clean error to the UI (e.g. model server down)
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


@app.post("/api/compare")
def compare(req: CompareRequest) -> dict:
    """Run the SAME task+attack under two configs (default baseline vs combined)
    and return both, for the side-by-side demo. Runs are sequential so each one's
    decision-log snapshot is clean; both use the same injection task."""
    try:
        injection = req.injection_task
        if injection is None:
            s = get_suite(BENCHMARK_VERSION, req.suite)
            injection = next(iter(s.injection_tasks.keys()))

        def go(config: str) -> dict:
            return run_single(
                suite=req.suite, user_task=req.user_task, config=config,
                model=req.model, model_id=req.model_id, attack=req.attack,
                injection_task=injection, escalate=req.escalate,
                benchmark_version=BENCHMARK_VERSION,
            )

        return {
            "attack": req.attack,
            "injection_task": injection,
            "left": go(req.left_config),
            "right": go(req.right_config),
        }
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
