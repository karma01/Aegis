"""Evaluation metrics — aggregate AgentDojo run results into the project's
success-criteria table across ablation configs.

Reads the per-task result JSONs that AgentDojo writes under ``runs/`` (each has
``utility``, ``security``, ``duration``, ``attack_type``, ``pipeline_name``) and
produces, per ablation config:

  * benign task utility       — mean utility on no-attack runs
  * utility under attack       — mean utility on attack runs
  * Attack Success Rate (ASR)  — 1 - mean(security) on attack runs
                                 (AgentDojo: security=True means the attack failed)
  * average latency (s)        — mean run duration
  * latency overhead vs baseline
  * utility drop vs baseline   — the over-block / false-positive proxy

This is the source of truth for the report's numbers and the data contract the
React dashboard will consume (see ``to_dict`` / ``--json``).

OWNER: Prashanna (Evaluation).

CLI:  python -m aegis.metrics --logdir ./runs [--baseline baseline] [--json]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

# Preferred row order in the printed table.
_CONFIG_ORDER = ["baseline", "moderator", "sandbox", "combined"]


def config_label(pipeline_name: str) -> str:
    """'vllm_parsed-aegis_combined' -> 'combined'; unprefixed names pass through."""
    if "aegis_" in pipeline_name:
        return pipeline_name.split("aegis_", 1)[1]
    return pipeline_name


def load_results(logdir: str | Path = "runs") -> list[dict]:
    """Load every AgentDojo result JSON under ``logdir`` (skips the JSONL log and
    any non-result JSON)."""
    results: list[dict] = []
    for path in Path(logdir).rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "utility" in data and "suite_name" in data:
            results.append(data)
    return results


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


@dataclass
class ConfigMetrics:
    config: str
    n_benign: int = 0
    n_attack: int = 0
    n_errors: int = 0
    benign_utility: float | None = None
    attack_utility: float | None = None
    asr: float | None = None
    avg_latency: float | None = None
    # filled by with_comparison(), relative to the baseline config:
    latency_overhead_pct: float | None = None
    utility_drop_pct: float | None = None


def aggregate(results: list[dict]) -> dict[str, ConfigMetrics]:
    """Group results by ablation config and compute per-config metrics."""
    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(config_label(r.get("pipeline_name", "?")), []).append(r)

    out: dict[str, ConfigMetrics] = {}
    for label, rs in groups.items():
        benign = [r for r in rs if not r.get("attack_type")]
        attack = [r for r in rs if r.get("attack_type")]
        durations = [r["duration"] for r in rs if isinstance(r.get("duration"), (int, float))]
        out[label] = ConfigMetrics(
            config=label,
            n_benign=len(benign),
            n_attack=len(attack),
            n_errors=sum(1 for r in rs if r.get("error")),
            benign_utility=_mean([1.0 if r.get("utility") else 0.0 for r in benign]) if benign else None,
            attack_utility=_mean([1.0 if r.get("utility") else 0.0 for r in attack]) if attack else None,
            # ASR = fraction of attack runs where the attack SUCCEEDED. AgentDojo's
            # `security` field IS the attack-success flag — it returns True when the
            # injection task was accomplished — so ASR = mean(security).
            asr=_mean([1.0 if r.get("security") else 0.0 for r in attack]) if attack else None,
            avg_latency=_mean(durations),
        )
    return out


def _pick_baseline(metrics: dict[str, ConfigMetrics]) -> str | None:
    for key in metrics:
        if "baseline" in key:
            return key
    return next(iter(metrics), None)


def with_comparison(
    metrics: dict[str, ConfigMetrics], baseline: str | None = None
) -> tuple[dict[str, ConfigMetrics], str | None]:
    """Fill latency-overhead and utility-drop fields relative to the baseline."""
    baseline = baseline or _pick_baseline(metrics)
    base = metrics.get(baseline) if baseline else None
    for m in metrics.values():
        if base and base.avg_latency and m.avg_latency is not None:
            m.latency_overhead_pct = (m.avg_latency / base.avg_latency - 1) * 100
        if base and base.benign_utility is not None and m.benign_utility is not None:
            m.utility_drop_pct = (base.benign_utility - m.benign_utility) * 100
    return metrics, baseline


# --- presentation -------------------------------------------------------------
def _ordered(metrics: dict[str, ConfigMetrics]) -> list[ConfigMetrics]:
    known = [metrics[c] for c in _CONFIG_ORDER if c in metrics]
    extra = [m for k, m in metrics.items() if k not in _CONFIG_ORDER]
    return known + extra


def _pct(x: float | None) -> str:
    return "  -  " if x is None else f"{x * 100:5.1f}%"


def _sec(x: float | None) -> str:
    return "  -  " if x is None else f"{x:6.2f}s"


def _signed_pct(x: float | None) -> str:
    # x is already in percentage points (e.g. 46.0 means +46.0%).
    return "  -  " if x is None else f"{x:+5.1f}%"


def format_table(metrics: dict[str, ConfigMetrics], baseline: str | None) -> str:
    header = (
        f"{'config':<10} {'benign':>7} {'atk-util':>8} {'ASR':>7} "
        f"{'latency':>8} {'lat_ovh':>7} {'util-drop':>9}  n(b/a)"
    )
    lines = [f"Ablation metrics (baseline = {baseline})", header, "-" * len(header)]
    for m in _ordered(metrics):
        lines.append(
            f"{m.config:<10} {_pct(m.benign_utility):>7} {_pct(m.attack_utility):>8} "
            f"{_pct(m.asr):>7} {_sec(m.avg_latency):>8} {_signed_pct(m.latency_overhead_pct):>7} "
            f"{_signed_pct(m.utility_drop_pct):>9}  {m.n_benign}/{m.n_attack}"
        )
    return "\n".join(lines)


def to_dict(metrics: dict[str, ConfigMetrics]) -> dict:
    return {k: asdict(v) for k, v in metrics.items()}


def compute(logdir: str | Path = "runs", baseline: str | None = None):
    metrics = aggregate(load_results(logdir))
    return with_comparison(metrics, baseline)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Aegis ablation metrics from a runs/ dir.")
    parser.add_argument("--logdir", default="runs")
    parser.add_argument("--baseline", default=None, help="Config label to use as baseline (default: auto).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    args = parser.parse_args()

    metrics, baseline = compute(args.logdir, args.baseline)
    if not metrics:
        print(f"No result files found under {args.logdir!r}.")
        return
    if args.json:
        print(json.dumps(to_dict(metrics), indent=2))
    else:
        print(format_table(metrics, baseline))


if __name__ == "__main__":
    main()
