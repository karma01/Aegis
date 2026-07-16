"""Run a single AgentDojo task through an Aegis pipeline and return the
conversation timeline + the Aegis decisions for that run.

Reuses the headless benchmark functions (so behaviour matches `run_aegis.py`),
then reads back the result JSON it wrote and the new lines appended to the
decision log. Requires the model server (Ollama / API) to be reachable.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from agentdojo.attacks.attack_registry import load_attack
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite

from aegis.contracts import Decision
from aegis.decision_log import DEFAULT_LOG_PATH
from aegis.pipeline import PRESETS, build_aegis_pipeline

_DECISIONS = Path(DEFAULT_LOG_PATH)


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def _decisions_since(start: int) -> list[dict]:
    if not _DECISIONS.exists():
        return []
    out: list[dict] = []
    with _DECISIONS.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < start or not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("content", "")))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return "" if content is None else str(content)

def _clean_messages(result: dict) -> list[dict]:
    """Normalise the saved conversation into a UI-friendly timeline."""
    timeline = []
    for m in result.get("messages", []):
        tool_calls = []
        for tc in m.get("tool_calls") or []:
            if isinstance(tc, dict):
                tool_calls.append({"function": tc.get("function"), "args": tc.get("args", {})})
            else:  # FunctionCall object
                tool_calls.append({"function": getattr(tc, "function", None), "args": getattr(tc, "args", {})})
        timeline.append(
            {
                "role": m.get("role"),
                "text": _text_of(m.get("content")),
                "tool_calls": tool_calls,
                "tool_call_id": m.get("tool_call_id"),
                "error": m.get("error"),
            }
        )
    return timeline

def _load_result(logdir: Path, pipeline_name: str, suite: str, user_task: str, attack: str, injection: str) -> dict:
    path = logdir / pipeline_name / suite / user_task / attack / f"{injection}.json"
    if not path.exists():
        raise FileNotFoundError(f"result not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_single(
    suite: str,
    user_task: str,
    config: str = "combined",
    model: str = "VLLM_PARSED",
    model_id: str | None = None,
    attack: str | None = None,
    injection_task: str | None = None,
    escalate: str = "block",
    benchmark_version: str = "v1.2.2",
    logdir: str = "runs",
) -> dict:
    load_dotenv(".env")
    if config not in PRESETS:
        raise ValueError(f"unknown config '{config}'")

    cfg = dataclasses.replace(
        PRESETS[config],
        escalate_action=Decision.BLOCK if escalate == "block" else Decision.ALLOW,
    )
    # Mirror run_aegis.py: a hosted OpenAI-compatible model (AEGIS_LLM_* in .env)
    # takes precedence over the local ModelsEnum path. Without this the UI falls
    # back to Ollama, which fails for models whose template lacks tool support.
    hosted_model = os.getenv("AEGIS_LLM_MODEL")
    base_url = os.getenv("AEGIS_LLM_BASE_URL")
    api_key = os.getenv("AEGIS_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    pipeline = build_aegis_pipeline(
        model, cfg, model_id=model_id, name_suffix=f"aegis_{config}",
        hosted_model=hosted_model, base_url=base_url, api_key=api_key,
    )
    suite_obj = get_suite(benchmark_version, suite)
    logdir_p = Path(logdir)
    start = _count_lines(_DECISIONS)

    with OutputLogger(str(logdir_p)):
        if attack:
            if injection_task is None:
                injection_task = next(iter(suite_obj.injection_tasks.keys()))
            attacker = load_attack(attack, suite_obj, pipeline)
            benchmark_suite_with_injections(
                pipeline, suite_obj, attacker,
                user_tasks=[user_task], injection_tasks=[injection_task],
                logdir=logdir_p, force_rerun=True, benchmark_version=benchmark_version,
            )
            attack_name, injection_name = attack, injection_task
        else:
            benchmark_suite_without_injections(
                pipeline, suite_obj, user_tasks=[user_task],
                logdir=logdir_p, force_rerun=True, benchmark_version=benchmark_version,
            )
            attack_name, injection_name = "none", "none"

    result = _load_result(logdir_p, pipeline.name, suite, user_task, attack_name, injection_name)
    return {
        "pipeline": pipeline.name,
        "config": config,
        "result": {
            "utility": result.get("utility"),
            "security": result.get("security"),
            "duration": result.get("duration"),
            "error": result.get("error"),
            "attack": attack,
            "injection_task": None if not attack else injection_name,
        },
        "messages": _clean_messages(result),
        "decisions": _decisions_since(start),
    }
