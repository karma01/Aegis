"""Layer 4 — Capability/egress sandbox + enforcement point  [STUB — Week 3, owner: Asmita]

Replaces AgentDojo's ToolsExecutor. It is the single place where Aegis *enforces*
the verdicts recorded by the moderator/gate, and where tool execution is
(optionally) isolated.

This stub executes tool calls normally (so the agent loop runs) but does NOT yet
enforce verdicts or isolate execution. TODO (Asmita): implement
  - enforcement: read verdicts from extra_args (aegis.contracts.verdict_for) and,
    for BLOCK/ESCALATE, return a synthetic "blocked" tool result instead of
    executing — while keeping a result for every tool_call (the OpenAI/VLLM_PARSED
    native path requires it),
  - a capability/egress boundary that denies exfiltration on tainted context,
    with its own taint signal (defense in depth).
See the reference implementation on the `master` prototype branch.
"""

from __future__ import annotations

from ast import literal_eval
from collections.abc import Callable, Sequence

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.llms.google_llm import EMPTY_FUNCTION_NAME
from agentdojo.agent_pipeline.tool_execution import is_string_list, tool_result_to_str
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionReturnType, FunctionsRuntime
from agentdojo.types import ChatMessage, ChatToolResultMessage, text_content_block_from_string

from aegis.contracts import Decision
from aegis.decision_log import DecisionLogger, get_logger


class AegisToolsExecutor(BasePipelineElement):
    name = "aegis_tools_executor"

    def __init__(
        self,
        output_formatter: Callable[[FunctionReturnType], str] = tool_result_to_str,
        sandbox: bool = False,
        escalate_action: Decision = Decision.BLOCK,
        logger: DecisionLogger | None = None,
    ) -> None:
        self.output_formatter = output_formatter
        self.sandbox = sandbox
        self.escalate_action = escalate_action
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

        results: list[ChatToolResultMessage] = []
        for tool_call in tool_calls:
            # TODO (Asmita): consult extra_args verdicts here and skip execution for
            # BLOCK/ESCALATE; optionally run inside an isolated sandbox.
            results.append(self._execute(tool_call, runtime, env))
        return query, runtime, env, [*messages, *results], extra_args

    def _execute(self, tool_call: FunctionCall, runtime: FunctionsRuntime, env: Env) -> ChatToolResultMessage:
        if tool_call.function == EMPTY_FUNCTION_NAME:
            return self._result(tool_call, "", error="Empty function name provided. Provide a valid function name.")
        if tool_call.function not in (tool.name for tool in runtime.functions.values()):
            return self._result(tool_call, "", error=f"Invalid tool {tool_call.function} provided.")
        for arg_k, arg_v in tool_call.args.items():
            if isinstance(arg_v, str) and is_string_list(arg_v):
                tool_call.args[arg_k] = literal_eval(arg_v)
        tool_result, error = runtime.run_function(env, tool_call.function, tool_call.args)
        return self._result(tool_call, self.output_formatter(tool_result), error=error)

    def _result(self, tool_call: FunctionCall, content: str, error: str | None) -> ChatToolResultMessage:
        return ChatToolResultMessage(
            role="tool",
            content=[text_content_block_from_string(content)],
            tool_call_id=tool_call.id,
            tool_call=tool_call,
            error=error,
        )
