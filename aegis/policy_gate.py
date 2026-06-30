"""Layer 3 — Lethal-trifecta policy gate  [STUB — Week 3, owner: Asmita]

Enforces the lethal-trifecta rule: a high-risk *exfiltration* action that depends
on *tainted* data must be blocked or escalated. Runs BEFORE execution (after the
moderator) and records verdicts; the executor enforces them.

``decide(tool_call, taint_state) -> Decision`` is the STABLE cross-module contract
(taint tracker -> policy gate). Keep its signature stable — other modules and the
tests depend on it.

This is a no-op stub: ``decide`` always returns ALLOW. TODO (Asmita): implement
  - an egress/exfiltration capability check (which tools send data out),
  - return ESCALATE/BLOCK when an egress action runs on a tainted context,
  - record verdicts in the element's query().
See the reference implementation on the `master` prototype branch.
"""

from __future__ import annotations

from collections.abc import Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionsRuntime
from agentdojo.types import ChatMessage

from aegis.contracts import Decision, TaintState
from aegis.decision_log import DecisionLogger, get_logger


def decide(
    tool_call: FunctionCall,
    taint_state: TaintState,
    on_violation: Decision = Decision.ESCALATE,
) -> Decision:
    """STABLE CONTRACT (taint tracker -> policy gate). Stub: always ALLOW.

    TODO (Asmita): return ``on_violation`` when ``tool_call`` is an egress action
    AND ``taint_state.tainted`` (untrusted data + exfiltration path)."""
    return Decision.ALLOW


class AegisPolicyGate(BasePipelineElement):
    name = "aegis_policy_gate"

    def __init__(self, on_violation: Decision = Decision.ESCALATE, logger: DecisionLogger | None = None) -> None:
        self.on_violation = on_violation
        self.logger = logger or get_logger()

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        # TODO (Asmita): for each proposed tool call, call decide(tc, taint) and
        # record any ESCALATE/BLOCK verdict into extra_args.
        return query, runtime, env, messages, extra_args
