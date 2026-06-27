"""Aegis — a taint-aware agentic moderator and sandbox framework for defending
tool-using LLM agents against prompt injection, implemented as AgentDojo pipeline
elements.

The four layers are independent ``BasePipelineElement``s inserted into a
``ToolsExecutionLoop`` (see :mod:`aegis.pipeline`):

1. :class:`aegis.moderator.AegisModerator`     — risk decision per proposed tool call
2. :class:`aegis.taint.AegisTaintTracker`      — coarse trusted/untrusted labelling
3. :class:`aegis.policy_gate.AegisPolicyGate`  — lethal-trifecta rule (``decide``)
4. :class:`aegis.sandbox.AegisToolsExecutor`   — isolated execution + enforcement

Because AgentDojo's ``--defense`` flag only accepts its built-in names, Aegis is
selected via the project's own runner (``run_aegis.py``), not ``--defense``.
"""

from aegis.contracts import Decision, TaintState
from aegis.pipeline import PRESETS, AegisConfig, build_aegis_pipeline

__all__ = ["Decision", "TaintState", "AegisConfig", "PRESETS", "build_aegis_pipeline"]
