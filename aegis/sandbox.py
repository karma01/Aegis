"""Layer 4 — capability/egress sandbox + decision enforcement point.

This replaces AgentDojo's ``ToolsExecutor``. It does two jobs:

1. **Enforcement** — it is the single place where the verdicts recorded by the
   moderator and policy gate are applied (ALLOW / BLOCK / ESCALATE), so every
   ``tool_call`` keeps a matching tool result (the OpenAI/``VLLM_PARSED`` native
   path requires this).

2. **Capability sandbox** (when ``sandbox=True``) — an *independent* containment
   boundary at the moment of execution: an egress/exfiltration capability is
   denied once the sandbox has itself observed untrusted data, regardless of what
   the upstream layers decided. It maintains its **own** taint signal (via the
   trust labeler), so it still contains an attack in the sandbox-only ablation,
   and even if the moderator LLM is itself injected.

Why capability-based and not a micro-VM: AgentDojo's tools mutate an in-memory
synthetic environment (no real host/network), so a micro-VM has nothing real to
isolate and the benchmark can't score host compromise. Capability-based egress
containment is the form of isolation that is both implementable and *measurable*
here. A third-party micro-VM is documented as production future-work.

OWNER: Asmita (Containment).
"""

from __future__ import annotations

from ast import literal_eval
from collections.abc import Callable, Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.llms.google_llm import EMPTY_FUNCTION_NAME
from agentdojo.agent_pipeline.tool_execution import is_string_list, tool_result_to_str
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionReturnType, FunctionsRuntime
from agentdojo.types import ChatMessage, ChatToolResultMessage, get_text_content_as_str, text_content_block_from_string

from aegis.contracts import Decision, get_decisions, verdict_for
from aegis.decision_log import DecisionLogger, get_logger
from aegis.trust import TrustLabeler, default_labeler

# Egress = a capability that can send data OUT of the agent's boundary. Narrower
# than the policy gate's "high-risk" set (which also covers local mutation).
EGRESS_KEYWORDS = {"send", "post", "share", "invite", "transfer", "pay", "publish", "upload"}

# extra_args key for the sandbox's own, layer-independent taint signal.
SANDBOX_KEY = "aegis_sandbox"


def is_egress(tool_name: str) -> bool:
    name = tool_name.lower()
    return any(keyword in name for keyword in EGRESS_KEYWORDS)


class CapabilitySandbox:
    """Self-contained egress containment with its own taint signal."""

    def __init__(self, labeler: TrustLabeler | None = None) -> None:
        self.labeler = labeler or default_labeler

    def _state(self, extra_args: dict) -> dict:
        st = extra_args.get(SANDBOX_KEY)
        if not isinstance(st, dict):
            st = {"tainted": False, "sources": set()}
            extra_args[SANDBOX_KEY] = st
        return st

    def check(self, tool_call: FunctionCall, extra_args: dict) -> tuple[bool, str]:
        """Permit/deny a call *before* execution."""
        st = self._state(extra_args)
        if is_egress(tool_call.function) and st["tainted"]:
            return False, f"egress capability '{tool_call.function}' denied on sandbox-tainted context {sorted(st['sources'])}"
        return True, "capability permitted"

    def observe(self, tool_call: FunctionCall, content: str, extra_args: dict) -> None:
        """Update the sandbox's own taint signal from a tool's output."""
        untrusted, _ = self.labeler.label(tool_call.function, content)
        if untrusted:
            st = self._state(extra_args)
            st["tainted"] = True
            st["sources"].add(tool_call.function)


class AegisToolsExecutor(BasePipelineElement):
    name = "aegis_tools_executor"

    def __init__(
        self,
        output_formatter: Callable[[FunctionReturnType], str] = tool_result_to_str,
        sandbox: bool = False,
        escalate_action: Decision = Decision.BLOCK,
        labeler: TrustLabeler | None = None,
        logger: DecisionLogger | None = None,
    ) -> None:
        self.output_formatter = output_formatter
        self.sandbox = sandbox
        self.escalate_action = escalate_action
        self.capability_sandbox = CapabilitySandbox(labeler)
        self.logger = logger or get_logger()

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        if not messages or messages[-1].get("role") != "assistant":
            return query, runtime, env, messages, extra_args
        tool_calls = messages[-1].get("tool_calls")
        if not tool_calls:
            return query, runtime, env, messages, extra_args

        decisions = get_decisions(extra_args)
        results: list[ChatToolResultMessage] = []

        for tool_call in tool_calls:
            # 1) Enforce upstream (moderator / gate) verdicts.
            verdict = verdict_for(decisions, tool_call.id)
            effective = verdict.decision
            if effective is Decision.ESCALATE:
                effective = self.escalate_action  # no human in the benchmark loop
            if effective is not Decision.ALLOW:
                results.append(self._denied(tool_call, verdict.decision, verdict.reason))
                self.logger.log(
                    layer="enforcement", tool=tool_call.function, call_id=tool_call.id,
                    enforced=effective.value, original=verdict.decision.value, reason=verdict.reason,
                )
                continue

            # 2) Capability sandbox (independent containment at execution time).
            if self.sandbox:
                permitted, reason = self.capability_sandbox.check(tool_call, extra_args)
                if not permitted:
                    results.append(self._denied(tool_call, Decision.BLOCK, reason, source="sandbox"))
                    self.logger.log(
                        layer="sandbox", tool=tool_call.function, call_id=tool_call.id,
                        enforced="BLOCK", reason=reason,
                    )
                    continue

            # 3) Execute, then let the sandbox observe the output for its taint signal.
            message = self._execute(tool_call, runtime, env)
            if self.sandbox:
                self.capability_sandbox.observe(
                    tool_call, get_text_content_as_str(message["content"] or []), extra_args
                )
            results.append(message)

        decisions.clear()  # verdicts are per-turn
        return query, runtime, env, [*messages, *results], extra_args

    # -- execution ---------------------------------------------------------
    def _execute(self, tool_call: FunctionCall, runtime: FunctionsRuntime, env: Env) -> ChatToolResultMessage:
        if tool_call.function == EMPTY_FUNCTION_NAME:
            return self._result(tool_call, "", error="Empty function name provided. Provide a valid function name.")
        if tool_call.function not in (tool.name for tool in runtime.functions.values()):
            return self._result(tool_call, "", error=f"Invalid tool {tool_call.function} provided.")

        # Coerce stringified lists to real lists (mirrors AgentDojo's ToolsExecutor).
        for arg_k, arg_v in tool_call.args.items():
            if isinstance(arg_v, str) and is_string_list(arg_v):
                tool_call.args[arg_k] = literal_eval(arg_v)

        tool_result, error = runtime.run_function(env, tool_call.function, tool_call.args)
        return self._result(tool_call, self.output_formatter(tool_result), error=error)

    # -- helpers -----------------------------------------------------------
    def _denied(self, tool_call: FunctionCall, decision: Decision, reason: str, source: str = "Aegis") -> ChatToolResultMessage:
        text = f"[{source.upper()}] Tool call '{tool_call.function}' was {decision.value}: {reason}"
        return self._result(tool_call, text, error=f"{source.upper()}_{decision.value}: {reason}")

    def _result(self, tool_call: FunctionCall, content: str, error: str | None) -> ChatToolResultMessage:
        return ChatToolResultMessage(
            role="tool",
            content=[text_content_block_from_string(content)],
            tool_call_id=tool_call.id,
            tool_call=tool_call,
            error=error,
        )
