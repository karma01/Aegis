"""Full-scale ablation harness — runs the whole benchmark matrix, survives
rate limits, and prints a statistically-grounded report.

For each config (baseline/moderator/sandbox/combined) x suite it runs the benign
utility set and the attack set, retrying with backoff on RateLimitError and
resuming from the ``runs/`` cache (so you can stop and restart freely). At the
end it prints the ablation table with 95% Wilson confidence intervals and a
paired McNemar significance test vs. baseline.

Uses the hosted model from .env (AEGIS_LLM_*), same as run_aegis.py.

Examples (PowerShell):
    # A feasible representative sample across all suites
    python run_ablation.py

    # Everything, workspace only
    python run_ablation.py -s workspace --limit-user 0 --limit-injection 0
"""

from __future__ import annotations

import os
import time
import warnings
from pathlib import Path

import click
from dotenv import load_dotenv
from openai import RateLimitError
from rich import print

from agentdojo.attacks.attack_registry import load_attack
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite

from aegis.contracts import Decision
from aegis.pipeline import PRESETS, build_aegis_pipeline
from aegis.stats import format_report

ALL_SUITES = ["workspace", "banking", "travel", "slack"]


def _retry(label: str, fn, max_retries: int, base_sleep: int):
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except RateLimitError:
            wait = base_sleep * attempt
            print(f"  [yellow]rate limited[/yellow] on {label}; sleeping {wait}s "
                  f"(attempt {attempt}/{max_retries}, resumes from cache)")
            time.sleep(wait)
    print(f"  [red]giving up on {label} after {max_retries} retries[/red]")
    return None


def _cap(items: list[str], limit: int) -> list[str] | None:
    if limit and limit > 0:
        return sorted(items)[:limit]
    return None  # None => all


def main_impl(suites, configs, attack, model, model_id, limit_user, limit_injection,
              logdir, benchmark_version, escalate, max_retries, base_sleep):
    load_dotenv(".env")
    hosted_model = os.getenv("AEGIS_LLM_MODEL")
    base_url = os.getenv("AEGIS_LLM_BASE_URL")
    api_key = os.getenv("AEGIS_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    escalate_action = Decision.BLOCK if escalate == "block" else Decision.ALLOW
    logdir = Path(logdir)

    def build(cfg_name):
        cfg = PRESETS[cfg_name]
        cfg.escalate_action = escalate_action
        kw = dict(model_id=model_id, name_suffix=f"aegis_{cfg_name}")
        if hosted_model:
            kw.update(hosted_model=hosted_model, base_url=base_url, api_key=api_key)
        return build_aegis_pipeline(model, cfg, **kw)

    print(f"[bold]Ablation[/bold] suites={list(suites)} configs={list(configs)} "
          f"attack={attack or 'none'} model={hosted_model or model}")

    for suite_name in suites:
        suite = get_suite(benchmark_version, suite_name)
        uts = _cap(list(suite.user_tasks.keys()), limit_user)
        its = _cap(list(suite.injection_tasks.keys()), limit_injection)
        for cfg_name in configs:
            pipeline = build(cfg_name)
            print(f"[cyan]▶ {suite_name} / {cfg_name}[/cyan] ({pipeline.name})")
            with OutputLogger(str(logdir)):
                # benign utility
                _retry(f"{suite_name}/{cfg_name}/benign", lambda: benchmark_suite_without_injections(
                    pipeline, suite, user_tasks=uts, logdir=logdir,
                    force_rerun=False, benchmark_version=benchmark_version), max_retries, base_sleep)
                # under attack
                if attack:
                    attacker = load_attack(attack, suite, pipeline)
                    _retry(f"{suite_name}/{cfg_name}/attack", lambda: benchmark_suite_with_injections(
                        pipeline, suite, attacker, user_tasks=uts, injection_tasks=its, logdir=logdir,
                        force_rerun=False, benchmark_version=benchmark_version), max_retries, base_sleep)

    print("\n" + "=" * 60)
    report = format_report(str(logdir), baseline="baseline")
    print(report)
    report_path = logdir / "ablation_report.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n[green]saved[/green] {report_path}")


@click.command()
@click.option("--suite", "-s", "suites", multiple=True, help="Suites (default: all four).")
@click.option("--config", "-c", "configs", multiple=True, help="Configs (default: all presets).")
@click.option("--attack", default="important_instructions", help="Attack name (or 'none' for benign only).")
@click.option("--model", default="VLLM_PARSED", help="Local ModelsEnum name if not using a hosted model.")
@click.option("--model-id", default=None)
@click.option("--limit-user", default=5, type=int, help="Max user tasks per suite (0 = all).")
@click.option("--limit-injection", default=3, type=int, help="Max injection tasks per suite (0 = all).")
@click.option("--logdir", default="./runs", type=str)
@click.option("--benchmark-version", default="v1.2.2")
@click.option("--escalate", type=click.Choice(["block", "allow"]), default="block")
@click.option("--max-retries", default=8, type=int, help="Rate-limit retries per slice.")
@click.option("--base-sleep", default=20, type=int, help="Backoff base seconds (grows linearly).")
def main(suites, configs, attack, model, model_id, limit_user, limit_injection,
         logdir, benchmark_version, escalate, max_retries, base_sleep):
    if not load_dotenv(".env"):
        warnings.warn("No .env file found")
    suites = suites or tuple(ALL_SUITES)
    configs = configs or tuple(PRESETS)
    for c in configs:
        if c not in PRESETS:
            raise SystemExit(f"Unknown config '{c}'. Choose from {', '.join(PRESETS)}.")
    attack_name = None if attack == "none" else attack
    main_impl(suites, configs, attack_name, model, model_id, limit_user, limit_injection,
              logdir, benchmark_version, escalate, max_retries, base_sleep)


if __name__ == "__main__":
    main()
