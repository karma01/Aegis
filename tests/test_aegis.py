"""Offline foundation tests for the Aegis Week-1 scaffold (no model/server needed).

These cover the *contracts* and the *seams* — not layer logic, which is stubbed
(see per-owner TODOs in each aegis/ module). As layers are implemented, add their
behaviour tests here.

Run:  python tests/test_aegis.py    (or: python -m pytest tests/)
"""

from __future__ import annotations

from agentdojo.functions_runtime import FunctionCall

from aegis.contracts import Decision, TaintState, get_decisions, record_decision, verdict_for
from aegis.moderator import AegisModerator
from aegis.policy_gate import AegisPolicyGate, decide
from aegis.sandbox import AegisToolsExecutor
from aegis.taint import AegisTaintTracker


class _FakeFn:
    def __init__(self, name):
        self.name = name


class _FakeRuntime:
    def __init__(self, names):
        self.functions = {n: _FakeFn(n) for n in names}
        self.executed = []

    def run_function(self, env, name, args):
        self.executed.append(name)
        return f"ran {name}", None


def _assistant(tool_calls):
    return {"role": "assistant", "content": [], "tool_calls": tool_calls}


def test_contracts():
    ts = TaintState()
    assert not ts.tainted
    assert ts.mark("emails") is True and ts.tainted
    d = {}
    record_decision(d, "1", Decision.ALLOW, "ok", "moderator")
    record_decision(d, "1", Decision.BLOCK, "bad", "gate")  # highest severity wins
    assert verdict_for(d, "1").decision is Decision.BLOCK
    assert verdict_for(d, "missing").decision is Decision.ALLOW
    print("ok  contracts (Decision / TaintState / record_decision)")


def test_decide_stub_allows():
    send = FunctionCall(function="send_email", args={}, id="1")
    assert decide(send, TaintState(tainted=True)) is Decision.ALLOW
    print("ok  policy-gate decide() stub returns ALLOW (TODO: implement trifecta)")


def test_stub_layers_are_noop():
    extra = {}
    msgs = [_assistant([FunctionCall(function="read_inbox", args={}, id="9")])]
    for elem in (AegisModerator(), AegisPolicyGate(), AegisTaintTracker()):
        _, _, _, out, extra = elem.query("q", _FakeRuntime(["read_inbox"]), None, msgs, extra)
        assert out is msgs, f"{elem.name} stub must pass messages through unchanged"
    assert get_decisions(extra) == {}, "stubs record no verdicts yet"
    print("ok  moderator/gate/taint stubs are no-ops")


def test_executor_runs_tools():
    extra = {}
    rt = _FakeRuntime(["read_inbox"])
    _, _, _, out, extra = AegisToolsExecutor().query(
        "q", rt, None, [_assistant([FunctionCall(function="read_inbox", args={}, id="9")])], extra
    )
    assert rt.executed == ["read_inbox"] and out[-1]["role"] == "tool"
    print("ok  executor runs tool calls (agent loop stays functional)")


def test_pipeline_assembles():
    import agentdojo.agent_pipeline.agent_pipeline as ap

    ap._get_local_model_id = lambda port: "llama3.1:latest"  # avoid the /v1/models probe
    from aegis.pipeline import PRESETS, build_aegis_pipeline

    for name, cfg in PRESETS.items():
        p = build_aegis_pipeline("VLLM_PARSED", cfg, name_suffix=f"aegis_{name}")
        assert p.name.endswith(f"aegis_{name}")
    print("ok  all four ablation presets assemble")


if __name__ == "__main__":
    test_contracts()
    test_decide_stub_allows()
    test_stub_layers_are_noop()
    test_executor_runs_tools()
    test_pipeline_assembles()
    print("\nAll Aegis foundation tests passed.")
