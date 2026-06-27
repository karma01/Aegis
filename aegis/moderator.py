"""Layer 1 — agentic moderator.

Runs BEFORE the executor. For each proposed tool call it produces a verdict
(ALLOW / BLOCK / ESCALATE) from two signals:

  * deterministic policy rules (fast, auditable, never injected), and
  * a lightweight LLM-as-judge risk score (defence in depth — but the final
    decision never relies on the judge alone).

The verdict is recorded into ``extra_args``; the executor enforces it. This
element never executes or mutates tool calls itself.

OWNER: Pawan (Detection).
"""

from __future__ import annotations

from collections.abc import Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionsRuntime
from agentdojo.types import ChatMessage

from aegis.contracts import Decision, get_decisions, get_taint, record_decision
from aegis.decision_log import DecisionLogger, get_logger
from aegis.judge import LLMJudge
from aegis.policy_gate import is_high_risk

# Deterministic rule: tool names that are never allowed regardless of taint.
# TODO (Pawan): tune per suite; this is a conservative starter set.
HARD_BLOCK_TOOLS: set[str] = set()


class AegisModerator(BasePipelineElement):
    name = "aegis_moderator"

    def __init__(
        self,
        risk_threshold: float = 0.7,
        llm_judge: LLMJudge | None = None,
        use_judge: bool = True,
        logger: DecisionLogger | None = None,
    ) -> None:
        self.risk_threshold = risk_threshold
        # An object with a ``score(tool_call, taint, messages) -> float`` method.
        # Defaults to the LLM judge; pass use_judge=False (or a fake) to disable.
        if llm_judge is None and use_judge:
            llm_judge = LLMJudge()
        self.llm_judge = llm_judge
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
            decision, reason, risk = self._moderate(tool_call, taint, messages)
            record_decision(decisions, tool_call.id, decision, reason, layer="moderator")
            self.logger.log(
                layer="moderator",
                tool=tool_call.function,
                call_id=tool_call.id,
                decision=decision.value,
                risk=risk,
                tainted=taint.tainted,
                reason=reason,
            )

        return query, runtime, env, messages, extra_args

    def _moderate(self, tool_call: FunctionCall, taint, messages) -> tuple[Decision, str, float]:
        # 1) Deterministic rules — auditable, cannot be talked out of by an injection.
        if tool_call.function in HARD_BLOCK_TOOLS:
            return Decision.BLOCK, f"'{tool_call.function}' is on the hard-block list", 1.0

        # 2) LLM-as-judge risk score (defence in depth, advisory).
        risk = self._risk_score(tool_call, taint, messages)
        if risk >= self.risk_threshold:
            return Decision.ESCALATE, f"judge risk {risk:.2f} >= {self.risk_threshold}", risk

        return Decision.ALLOW, "no rule matched; risk below threshold", risk

    def _risk_score(self, tool_call: FunctionCall, taint, messages) -> float:
        """LLM-as-judge risk score in [0, 1] (advisory; combined with rules above).

        Cost control: only spend a judge call where risk is plausible — a
        high-impact action, or any action on a tainted context. Pure reads on a
        clean context score 0.0 without a model call."""
        if self.llm_judge is None:
            return 0.0
        if not (is_high_risk(tool_call) or taint.tainted):
            return 0.0
        return float(self.llm_judge.score(tool_call, taint, messages))
