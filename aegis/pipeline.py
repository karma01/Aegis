"""Assemble the Aegis pipeline and the ablation presets.

We start from AgentDojo's undefended pipeline (``defense=None``), reuse its
system-message / init-query / llm elements, and rebuild the ``ToolsExecutionLoop``
with the Aegis elements inserted in this order:

    Moderator -> PolicyGate -> AegisToolsExecutor(enforce + sandbox) -> TaintTracker -> llm

Detection elements run *before* execution (so they can flag calls); taint runs
*after* (so it labels fresh outputs and accumulates across turns). The executor
is the single enforcement point.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from agentdojo.agent_pipeline import AgentPipeline, OpenAILLM, PipelineConfig, ToolsExecutionLoop
from agentdojo.models import ModelsEnum

from aegis.contracts import Decision
from aegis.moderator import AegisModerator
from aegis.policy_gate import AegisPolicyGate
from aegis.sandbox import AegisToolsExecutor
from aegis.taint import AegisTaintTracker


@dataclass
class AegisConfig:
    """Which layers are active. Toggle these for ablations."""

    moderator: bool = True
    taint: bool = True
    policy_gate: bool = True
    sandbox: bool = False
    escalate_action: Decision = Decision.BLOCK

    @property
    def any_active(self) -> bool:
        return self.moderator or self.taint or self.policy_gate or self.sandbox


# The four ablation configurations from the project plan (CLAUDE.md "Evaluation").
PRESETS: dict[str, AegisConfig] = {
    # No defense — the true undefended baseline (plain AgentDojo pipeline).
    "baseline": AegisConfig(moderator=False, taint=False, policy_gate=False, sandbox=False),
    # Detection/decision stack, no isolation. Taint + gate feed the moderator's intent.
    "moderator": AegisConfig(moderator=True, taint=True, policy_gate=True, sandbox=False),
    # Containment only — capability sandbox with its own taint signal; no
    # moderator/gate/taint layers. Denies egress once it observes untrusted data.
    "sandbox": AegisConfig(moderator=False, taint=False, policy_gate=False, sandbox=True),
    # Everything on.
    "combined": AegisConfig(moderator=True, taint=True, policy_gate=True, sandbox=True),
}


def _make_hosted_llm(model: str, base_url: str | None, api_key: str | None) -> OpenAILLM:
    """Build an OpenAI-compatible LLM element pointed at any hosted endpoint
    (GitHub Models / Groq / OpenAI / ...). AgentDojo's built-in paths can't do
    this — `VLLM_PARSED` is localhost-only and the `openai` provider is locked to
    `ModelsEnum` names — but `PipelineConfig.llm` accepts a pre-built element."""
    import openai

    client = openai.OpenAI(base_url=base_url or None, api_key=api_key or os.getenv("OPENAI_API_KEY"))
    llm = OpenAILLM(client, model)  # self.model (the real id) is what's sent to the API
    llm.name = "hosted_" + model.replace("/", "_").replace(":", "_")  # filesystem-safe log path
    return llm


def build_aegis_pipeline(
    model: str,
    aegis_config: AegisConfig,
    *,
    model_id: str | None = None,
    name_suffix: str = "aegis",
    tool_delimiter: str = "tool",
    hosted_model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> AgentPipeline:
    """Build an AgentDojo pipeline with the requested Aegis layers inserted.

    ``model`` is the UPPERCASE ``ModelsEnum`` *name* (e.g. ``"VLLM_PARSED"``) —
    the same convention the CLI requires (see CLAUDE.md). Pass ``hosted_model``
    (+ optional ``base_url``/``api_key``) to instead run against any
    OpenAI-compatible hosted endpoint. When no layers are active this returns the
    plain undefended pipeline unchanged.
    """
    llm_config = (
        _make_hosted_llm(hosted_model, base_url, api_key) if hosted_model else ModelsEnum[model].value
    )

    base = AgentPipeline.from_config(
        PipelineConfig(
            llm=llm_config,
            model_id=model_id,
            defense=None,
            tool_delimiter=tool_delimiter,
            system_message_name=None,
            system_message=None,
        )
    )

    if not aegis_config.any_active:
        base.name = f"{base.name}-{name_suffix}"  # distinct logdir/label for the baseline ablation
        return base  # undefended baseline

    # from_config (defense=None) yields [SystemMessage, InitQuery, llm, ToolsExecutionLoop]
    system_message, init_query, llm, _loop = list(base.elements)

    loop_elements = []
    if aegis_config.moderator:
        loop_elements.append(AegisModerator())
    if aegis_config.policy_gate:
        loop_elements.append(AegisPolicyGate(on_violation=Decision.ESCALATE))
    loop_elements.append(
        AegisToolsExecutor(sandbox=aegis_config.sandbox, escalate_action=aegis_config.escalate_action)
    )
    if aegis_config.taint:
        loop_elements.append(AegisTaintTracker())
    loop_elements.append(llm)

    pipeline = AgentPipeline([system_message, init_query, llm, ToolsExecutionLoop(loop_elements)])
    pipeline.name = f"{base.name}-{name_suffix}"
    return pipeline
