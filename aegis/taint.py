"""Layer 2 — coarse-grained taint tracking.

Runs AFTER the executor in the loop, so it sees the freshly-appended tool-result
messages. It asks the trust-label model (:mod:`aegis.trust`) whether each tool
output is untrusted and, on any untrusted output, marks the whole downstream
context tainted. The taint state lives in ``extra_args`` and is read by the
policy gate on later turns (taint accumulates across the conversation).

OWNER: Pawan (Detection).
"""

from __future__ import annotations

from collections.abc import Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.types import ChatMessage, get_text_content_as_str

from aegis.contracts import get_taint
from aegis.decision_log import DecisionLogger, get_logger
from aegis.trust import TrustLabeler, default_labeler


class AegisTaintTracker(BasePipelineElement):
    name = "aegis_taint_tracker"

    def __init__(
        self,
        labeler: TrustLabeler | None = None,
        logger: DecisionLogger | None = None,
    ) -> None:
        self.labeler = labeler or default_labeler
        self.logger = logger or get_logger()

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        taint = get_taint(extra_args)

        # Inspect the trailing run of tool-result messages (the batch the
        # executor just appended). Stop at the first non-tool message.
        for message in reversed(messages):
            if message.get("role") != "tool":
                break
            tool_call = message.get("tool_call")
            tool_name = tool_call.function if tool_call is not None else "unknown"
            content = get_text_content_as_str(message.get("content") or [])
            untrusted, reason = self.labeler.label(tool_name, content)
            self.logger.log(
                layer="taint",
                tool=tool_name,
                untrusted=untrusted,
                reason=reason,
                tainted=taint.tainted or untrusted,
                newly_tainted=untrusted and not taint.tainted,
            )
            if untrusted:
                taint.mark(tool_name)

        return query, runtime, env, messages, extra_args
