"""Layer 2 — Coarse-grained taint tracking + trust-label model  [STUB — Week 2, owner: Pawan]

Runs AFTER execution: labels each tool output trusted/untrusted (the trust-label
model) and, on any untrusted output, marks the whole downstream context tainted.
Taint state lives in ``extra_args`` (see aegis.contracts.get_taint) and
accumulates across turns, so a later "send" sees taint from an earlier read.

This is a no-op stub: it marks nothing. TODO (Pawan): implement
  - a trust-label model (build aegis/trust.py): which tool outputs are untrusted
    injection vectors (emails, web, files, reviews, ...) vs. safe,
  - mark taint via aegis.contracts.get_taint(extra_args).mark(source),
  - log via the decision logger.
See the reference implementation on the `master` prototype branch.
"""

from __future__ import annotations

from collections.abc import Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.types import ChatMessage

from aegis.decision_log import DecisionLogger, get_logger


class AegisTaintTracker(BasePipelineElement):
    name = "aegis_taint_tracker"

    def __init__(self, logger: DecisionLogger | None = None) -> None:
        self.logger = logger or get_logger()

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        # TODO (Pawan): scan the trailing tool-result messages, classify each
        # source with the trust-label model, and mark taint on untrusted output.
        return query, runtime, env, messages, extra_args
