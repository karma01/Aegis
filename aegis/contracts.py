"""Stable interface contracts shared across the Aegis layers.

These types are the seams the team agreed to keep stable (see CLAUDE.md /
Aegis_Project_Context.md). Detection writes verdicts; containment enforces them.
Do not change the shape of ``Decision``, ``TaintState``, or ``decide`` without
coordinating — every layer and the logging depend on them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# extra_args keys — Aegis state is threaded through the pipeline via extra_args
# (the dict passed between every BasePipelineElement.query call).
# ---------------------------------------------------------------------------
TAINT_KEY = "aegis_taint"
DECISIONS_KEY = "aegis_decisions"


class Decision(str, Enum):
    """The verdict for a single proposed tool call."""

    ALLOW = "ALLOW"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


# Severity ordering, so independent layers can only *raise* the severity of a
# verdict, never silently downgrade another layer's decision.
_SEVERITY = {Decision.ALLOW: 0, Decision.ESCALATE: 1, Decision.BLOCK: 2}


@dataclass
class TaintState:
    """Coarse-grained taint: once any untrusted tool output enters context, the
    whole downstream context is treated as tainted."""

    tainted: bool = False
    sources: set[str] = field(default_factory=set)

    def mark(self, source: str) -> bool:
        """Mark ``source`` as an untrusted contributor. Returns True if this call
        flipped the state from clean to tainted (useful for logging)."""
        newly = not self.tainted
        self.tainted = True
        self.sources.add(source)
        return newly


@dataclass
class Verdict:
    """A recorded decision for one tool call, with provenance for logging."""

    decision: Decision
    reason: str
    layer: str


# ---------------------------------------------------------------------------
# extra_args accessors — lazily initialise per-task state.
# ---------------------------------------------------------------------------
def get_taint(extra_args: dict) -> TaintState:
    ts = extra_args.get(TAINT_KEY)
    if not isinstance(ts, TaintState):
        ts = TaintState()
        extra_args[TAINT_KEY] = ts
    return ts


def get_decisions(extra_args: dict) -> dict[str, Verdict]:
    d = extra_args.get(DECISIONS_KEY)
    if not isinstance(d, dict):
        d = {}
        extra_args[DECISIONS_KEY] = d
    return d


def record_decision(
    decisions: dict[str, Verdict], call_id: str | None, decision: Decision, reason: str, layer: str
) -> Verdict:
    """Record a verdict for ``call_id``, keeping only the highest-severity verdict
    so one layer cannot weaken another's. ``call_id`` may be None (rare); we key
    on a stable fallback in that case."""
    key = call_id if call_id is not None else "__no_id__"
    current = decisions.get(key)
    if current is None or _SEVERITY[decision] > _SEVERITY[current.decision]:
        decisions[key] = Verdict(decision=decision, reason=reason, layer=layer)
    return decisions[key]


def verdict_for(decisions: dict[str, Verdict], call_id: str | None) -> Verdict:
    """The effective verdict for a call id; ALLOW if no layer recorded one."""
    key = call_id if call_id is not None else "__no_id__"
    return decisions.get(key, Verdict(Decision.ALLOW, "no Aegis layer flagged this call", "default"))
