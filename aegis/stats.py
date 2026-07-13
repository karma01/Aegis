"""Statistical rigor for the ablation — confidence intervals + significance.

Turns point estimates ("ASR 0%") into defensible claims:
  - Wilson score confidence intervals for the ASR / utility proportions,
  - an exact McNemar test for the *paired* baseline-vs-defended comparison on the
    same (suite, user_task, injection_task) items (the right test for two
    classifiers on the same examples).

Pure-stdlib (uses math.comb) — no scipy dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from aegis.metrics import config_label, load_results


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n (default 95%)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact_p(b: int, c: int) -> float:
    """Exact (binomial) two-sided McNemar p-value for discordant counts b, c.

    b, c are the off-diagonal cells: cases where exactly one of the two conditions
    succeeded. Under H0 each discordant case is a fair coin, so
    p = 2 * P(X <= min(b,c)) with X ~ Binomial(b+c, 0.5), capped at 1."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def _key(r: dict) -> tuple:
    return (r.get("suite_name"), r.get("user_task_id"), r.get("injection_task_id"))


@dataclass
class ConfigStats:
    config: str
    asr: float | None
    asr_ci: tuple[float, float] | None
    n_attack: int
    benign_utility: float | None
    benign_ci: tuple[float, float] | None
    n_benign: int


@dataclass
class PairedTest:
    baseline: str
    other: str
    n_paired: int
    baseline_attacks: int          # attacks that succeeded under baseline
    other_attacks: int             # attacks that succeeded under `other`
    fixed_by_defense: int          # baseline succeeded, defended blocked (b)
    broken_by_defense: int         # baseline blocked, defended succeeded (c)
    p_value: float
    significant: bool              # p < 0.05


def config_stats(results: list[dict]) -> dict[str, ConfigStats]:
    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(config_label(r.get("pipeline_name", "?")), []).append(r)

    out: dict[str, ConfigStats] = {}
    for label, rs in groups.items():
        attack = [r for r in rs if r.get("attack_type")]
        benign = [r for r in rs if not r.get("attack_type") and str(r.get("user_task_id", "")).startswith("user_task")]
        asr_k = sum(1 for r in attack if r.get("security"))  # security True => attack succeeded
        ben_k = sum(1 for r in benign if r.get("utility"))
        out[label] = ConfigStats(
            config=label,
            asr=(asr_k / len(attack)) if attack else None,
            asr_ci=wilson_ci(asr_k, len(attack)) if attack else None,
            n_attack=len(attack),
            benign_utility=(ben_k / len(benign)) if benign else None,
            benign_ci=wilson_ci(ben_k, len(benign)) if benign else None,
            n_benign=len(benign),
        )
    return out


def paired_test(results: list[dict], baseline: str, other: str) -> PairedTest | None:
    """McNemar on attack items shared by `baseline` and `other` configs."""
    base = {_key(r): bool(r.get("security")) for r in results
            if config_label(r.get("pipeline_name", "?")) == baseline and r.get("attack_type")}
    oth = {_key(r): bool(r.get("security")) for r in results
           if config_label(r.get("pipeline_name", "?")) == other and r.get("attack_type")}
    shared = set(base) & set(oth)
    if not shared:
        return None
    b = sum(1 for k in shared if base[k] and not oth[k])   # fixed by defense
    c = sum(1 for k in shared if not base[k] and oth[k])   # broken by defense
    p = mcnemar_exact_p(b, c)
    return PairedTest(
        baseline=baseline, other=other, n_paired=len(shared),
        baseline_attacks=sum(1 for k in shared if base[k]),
        other_attacks=sum(1 for k in shared if oth[k]),
        fixed_by_defense=b, broken_by_defense=c,
        p_value=p, significant=p < 0.05,
    )


def _pct(x: float | None) -> str:
    return "  -  " if x is None else f"{x * 100:.1f}%"


def _ci(ci: tuple[float, float] | None) -> str:
    return "" if ci is None else f"[{ci[0]*100:.0f}-{ci[1]*100:.0f}]"


def format_report(logdir: str = "runs", baseline: str = "baseline") -> str:
    results = load_results(logdir)
    if not results:
        return f"No result files under {logdir!r}."
    stats = config_stats(results)
    lines = ["Ablation with 95% Wilson CIs", f"{'config':<11}{'benign util':>16}{'ASR':>16}{'n(b/a)':>10}", "-" * 53]
    order = [c for c in ["baseline", "moderator", "sandbox", "combined"] if c in stats] + \
            [c for c in stats if c not in ("baseline", "moderator", "sandbox", "combined")]
    for c in order:
        s = stats[c]
        lines.append(f"{c:<11}{_pct(s.benign_utility)+' '+_ci(s.benign_ci):>16}{_pct(s.asr)+' '+_ci(s.asr_ci):>16}{f'{s.n_benign}/{s.n_attack}':>10}")

    lines += ["", "Paired significance vs baseline (McNemar, attack items):"]
    for c in order:
        if c == baseline:
            continue
        t = paired_test(results, baseline, c)
        if t is None:
            continue
        sig = "significant" if t.significant else "not significant"
        lines.append(
            f"  {baseline} vs {c}: {t.baseline_attacks}/{t.n_paired} -> {t.other_attacks}/{t.n_paired} attacks succeed; "
            f"fixed={t.fixed_by_defense}, regressed={t.broken_by_defense}, p={t.p_value:.4g} ({sig})"
        )
    return "\n".join(lines)
