"""Layer 1 — Agentic Moderator  [STUB — Week 2, owner: Pawan]

Intercepts each proposed tool call and decides ALLOW / BLOCK / ESCALATE from
deterministic policy rules + a lightweight LLM-as-judge risk score. Runs BEFORE
execution and only *records* verdicts into ``extra_args`` (the executor in
``aegis/sandbox.py`` enforces them).

This is a no-op stub: it currently records no verdicts (everything is allowed).
TODO (Pawan): implement
  - deterministic rules (e.g. hard-block lists),
  - a cost-gated LLM-as-judge risk score (build aegis/judge.py), with a safe
    fallback to 0.0 on any error,
  - record verdicts via aegis.contracts.record_decision(...).
See the reference implementation on the `master` prototype branch.
"""

from __future__ import annotations

from collections.abc import Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.types import ChatMessage

from aegis.decision_log import DecisionLogger, get_logger


class AegisModerator(BasePipelineElement):
    name = "aegis_moderator"

    def __init__(self, risk_threshold: float = 0.7, logger: DecisionLogger | None = None) -> None:
        self.risk_threshold = risk_threshold
        self.logger = logger or get_logger()

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        # TODO (Pawan): inspect messages[-1]["tool_calls"], score risk, and record
        # ALLOW/BLOCK/ESCALATE verdicts into extra_args via record_decision().
        return query, runtime, env, messages, extra_args
