"""Layer 3 — lethal-trifecta policy gate.

Runs BEFORE the executor (after the moderator). It enforces the rule at the
heart of the project: a high-risk *external/destructive* action that depends on
*tainted* data is the lethal trifecta (private data + untrusted content +
exfiltration) and must be blocked or escalated.

``decide(tool_call, taint_state)`` is the stable cross-module contract
(taint tracker -> policy gate) named in CLAUDE.md. Keep its signature stable.

OWNER: Asmita (Containment).
"""

from __future__ import annotations

from collections.abc import Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionsRuntime
from agentdojo.types import ChatMessage

from aegis.contracts import Decision, TaintState, get_decisions, get_taint, record_decision
from aegis.decision_log import DecisionLogger, get_logger

# Egress = capabilities that can send data OUT of the agent's trust boundary.
# The lethal trifecta is specifically about EXFILTRATION, so the gate keys on
# egress — NOT on local mutations (create/update/delete), which are a different
# threat class and over-block benign tasks when gated (measured: a legitimate
# create_calendar_event after reading the user's own calendar was being blocked).
# Note "email"/"message" are deliberately excluded so *reads* like
# get_received_emails / read_channel_messages don't count as egress.
# Destructive-action protection (e.g. injected delete) is separate future work.
# TODO (Asmita): replace heuristic with an explicit per-suite capability map.
EGRESS_KEYWORDS = {"send", "post", "share", "publish", "upload", "invite", "transfer", "pay"}


def is_egress(tool_call: FunctionCall) -> bool:
    """True if the call can send data outside the agent's boundary (exfiltration)."""
    name = tool_call.function.lower()
    return any(keyword in name for keyword in EGRESS_KEYWORDS)


# Backwards-compatible alias: the lethal-trifecta trigger is egress.
is_high_risk = is_egress


def decide(
    tool_call: FunctionCall,
    taint_state: TaintState,
    on_violation: Decision = Decision.ESCALATE,
) -> Decision:
    """STABLE CONTRACT (taint tracker -> policy gate).

    Lethal-trifecta verdict for one tool call: ALLOW unless the call is an
    *egress* action *and* the context is tainted (untrusted data + exfiltration
    path), in which case return ``on_violation`` (ESCALATE by default; BLOCK to
    deny outright)."""
    if is_egress(tool_call) and taint_state.tainted:
        return on_violation
    return Decision.ALLOW


class AegisPolicyGate(BasePipelineElement):
    name = "aegis_policy_gate"

    def __init__(
        self,
        on_violation: Decision = Decision.ESCALATE,
        logger: DecisionLogger | None = None,
    ) -> None:
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
        if not messages:
            return query, runtime, env, messages, extra_args
        last = messages[-1]
        if last.get("role") != "assistant" or not last.get("tool_calls"):
            return query, runtime, env, messages, extra_args

        taint = get_taint(extra_args)
        decisions = get_decisions(extra_args)

        for tool_call in last["tool_calls"]:
            decision = decide(tool_call, taint, on_violation=self.on_violation)
            if decision is not Decision.ALLOW:
                reason = f"lethal trifecta: egress '{tool_call.function}' on tainted context {sorted(taint.sources)}"
                record_decision(decisions, tool_call.id, decision, reason, layer="policy_gate")
                self.logger.log(
                    layer="policy_gate",
                    tool=tool_call.function,
                    call_id=tool_call.id,
                    decision=decision.value,
                    tainted=taint.tainted,
                    sources=sorted(taint.sources),
                    reason=reason,
                )

        return query, runtime, env, messages, extra_args
