"""Offline tests for the statistical layer (no model/server needed)."""

from __future__ import annotations

from aegis.stats import config_stats, mcnemar_exact_p, paired_test, wilson_ci


def test_wilson():
    lo, hi = wilson_ci(10, 10)
    assert hi == 1.0 and lo > 0.6, "10/10 -> upper bound 1, lower well above half"
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0 and hi < 0.35, "0/10 -> lower bound 0"
    assert wilson_ci(0, 0) == (0.0, 0.0)
    print("ok  wilson confidence interval")


def test_mcnemar():
    assert mcnemar_exact_p(0, 0) == 1.0
    assert mcnemar_exact_p(10, 0) < 0.05, "all discordant one way -> significant"
    assert mcnemar_exact_p(5, 5) > 0.5, "symmetric discordance -> not significant"
    print("ok  exact McNemar p-value")


def _r(cfg, ut, security):
    return {
        "pipeline_name": f"m-aegis_{cfg}", "suite_name": "workspace",
        "user_task_id": ut, "injection_task_id": "injection_task_0", "attack_type": "imp",
        "utility": True, "security": security, "duration": 1.0,
    }


def test_paired_and_config_stats():
    res = []
    for i in range(6):
        res.append(_r("baseline", f"user_task_{i}", True))   # attack succeeds undefended
        res.append(_r("combined", f"user_task_{i}", False))  # blocked with Aegis
    t = paired_test(res, "baseline", "combined")
    assert t.n_paired == 6 and t.fixed_by_defense == 6 and t.broken_by_defense == 0 and t.significant
    s = config_stats(res)
    assert s["baseline"].asr == 1.0 and s["combined"].asr == 0.0
    assert s["baseline"].asr_ci[0] > 0.5 and s["combined"].asr_ci[1] < 0.5
    print("ok  paired McNemar + per-config ASR/CI")


if __name__ == "__main__":
    test_wilson()
    test_mcnemar()
    test_paired_and_config_stats()
    print("\nAll stats tests passed.")
