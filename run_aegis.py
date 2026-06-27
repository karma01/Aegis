"""Aegis benchmark runner.

AgentDojo's ``--defense`` flag only accepts its built-in names, so Aegis is run
through this script instead: it builds the pipeline with the chosen Aegis layers
and calls AgentDojo's benchmark functions directly.

Examples (PowerShell; env vars come from .env):

    # One benign task, all layers
    python run_aegis.py -s workspace -ut user_task_0 --config combined

    # Run the full ablation (baseline, moderator, sandbox, combined) under attack
    python run_aegis.py -s workspace --attack important_instructions --config all -f

    # Just the undefended baseline on a strong API model
    python run_aegis.py -s banking --model GPT_4O_MINI_2024_07_18 --config baseline
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import click
from dotenv import load_dotenv
from rich import print

from agentdojo.attacks.attack_registry import load_attack
from agentdojo.benchmark import (
    SuiteResults,
    benchmark_suite_with_injections,
    benchmark_suite_without_injections,
)
from agentdojo.logging import OutputLogger
from agentdojo.models import ModelsEnum
from agentdojo.task_suite.load_suites import get_suite

from aegis.contracts import Decision
from aegis.pipeline import PRESETS, build_aegis_pipeline


def _show(suite_name: str, results: SuiteResults, security: bool) -> None:
    utilities = list(results["utility_results"].values())
    avg_utility = sum(utilities) / len(utilities) if utilities else 0.0
    print(f"[bold]{suite_name}[/bold]: utility {avg_utility * 100:.2f}%", end="")
    if security:
        sec = list(results["security_results"].values())
        # AgentDojo's `security` value is the attack-success flag (injection task
        # accomplished), so ASR = mean(security). Lower is better.
        asr = sum(sec) / len(sec) if sec else 0.0
        print(f" | ASR {asr * 100:.2f}%", end="")
    print()


def _run_one(
    config_name: str,
    model: str,
    model_id: str | None,
    suites: tuple[str, ...],
    user_tasks: tuple[str, ...],
    injection_tasks: tuple[str, ...],
    attack: str | None,
    logdir: Path,
    force_rerun: bool,
    benchmark_version: str,
    escalate_action: Decision,
    hosted_model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> None:
    cfg = PRESETS[config_name]
    cfg.escalate_action = escalate_action
    print(f"\n[bold cyan]=== Aegis config: {config_name} ===[/bold cyan] {cfg}")

    for suite_name in suites:
        suite = get_suite(benchmark_version, suite_name)
        pipeline = build_aegis_pipeline(
            model, cfg, model_id=model_id, name_suffix=f"aegis_{config_name}",
            hosted_model=hosted_model, base_url=base_url, api_key=api_key,
        )
        print(f"pipeline: {pipeline.name}")
        with OutputLogger(str(logdir)):
            if attack is None:
                results = benchmark_suite_without_injections(
                    pipeline,
                    suite,
                    user_tasks=user_tasks or None,
                    logdir=logdir,
                    force_rerun=force_rerun,
                    benchmark_version=benchmark_version,
                )
            else:
                attacker = load_attack(attack, suite, pipeline)
                results = benchmark_suite_with_injections(
                    pipeline,
                    suite,
                    attacker,
                    user_tasks=user_tasks or None,
                    injection_tasks=injection_tasks or None,
                    logdir=logdir,
                    force_rerun=force_rerun,
                    benchmark_version=benchmark_version,
                )
        _show(suite_name, results, security=attack is not None)


@click.command()
@click.option("--model", default="VLLM_PARSED", help="UPPERCASE ModelsEnum name (e.g. VLLM_PARSED, GPT_4O_MINI_2024_07_18). Ignored if --hosted-model is set.")
@click.option("--model-id", default=None, help="Model id for local models (used by LOCAL; ignored by VLLM_PARSED).")
@click.option("--hosted-model", default=None, help="Run against any OpenAI-compatible hosted endpoint (e.g. 'openai/gpt-4o-mini' on GitHub Models, 'llama-3.3-70b-versatile' on Groq). Defaults to env AEGIS_LLM_MODEL.")
@click.option("--base-url", default=None, help="Base URL for --hosted-model. Defaults to env AEGIS_LLM_BASE_URL.")
@click.option("--suite", "-s", "suites", multiple=True, help="Suite(s): workspace, banking, travel, slack.")
@click.option("--user-task", "-ut", "user_tasks", multiple=True)
@click.option("--injection-task", "-it", "injection_tasks", multiple=True)
@click.option("--attack", default=None, help="Attack name (omit for benign utility runs).")
@click.option("--config", "-c", "config_name", default="combined", help="Ablation preset: baseline | moderator | sandbox | combined | all.")
@click.option("--escalate", type=click.Choice(["block", "allow"]), default="block", help="What ESCALATE collapses to (no human in the loop).")
@click.option("--logdir", default="./runs", type=Path)
@click.option("--benchmark-version", default="v1.2.2")
@click.option("--force-rerun", "-f", is_flag=True)
def main(
    model: str,
    model_id: str | None,
    hosted_model: str | None,
    base_url: str | None,
    suites: tuple[str, ...],
    user_tasks: tuple[str, ...],
    injection_tasks: tuple[str, ...],
    attack: str | None,
    config_name: str,
    escalate: str,
    logdir: Path,
    benchmark_version: str,
    force_rerun: bool,
) -> None:
    if not load_dotenv(".env"):
        warnings.warn("No .env file found")

    # Hosted endpoint (GitHub Models / Groq / OpenAI / ...) takes precedence over
    # the local ModelsEnum paths. Defaults pulled from .env (AEGIS_LLM_*).
    hosted_model = hosted_model or os.getenv("AEGIS_LLM_MODEL")
    base_url = base_url or os.getenv("AEGIS_LLM_BASE_URL")
    api_key = os.getenv("AEGIS_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

    if hosted_model:
        print(f"[bold]Hosted model:[/bold] {hosted_model}  (base_url={base_url or 'default'})")
    else:
        # Validate the model name early with a clear message (the uppercase-name gotcha).
        try:
            ModelsEnum[model]
        except KeyError:
            raise SystemExit(
                f"Unknown model '{model}'. Pass the UPPERCASE enum NAME, e.g. VLLM_PARSED, LOCAL, "
                f"GPT_4O_MINI_2024_07_18 — not the hyphenated value. (Or use --hosted-model.)"
            )

    if not suites:
        raise SystemExit("Provide at least one --suite/-s (workspace | banking | travel | slack).")

    configs = list(PRESETS) if config_name == "all" else [config_name]
    for name in configs:
        if name not in PRESETS:
            raise SystemExit(f"Unknown --config '{name}'. Choose from: {', '.join(PRESETS)} | all")

    escalate_action = Decision.BLOCK if escalate == "block" else Decision.ALLOW
    for name in configs:
        _run_one(
            name, model, model_id, suites, user_tasks, injection_tasks,
            attack, logdir, force_rerun, benchmark_version, escalate_action,
            hosted_model=hosted_model, base_url=base_url, api_key=api_key,
        )


if __name__ == "__main__":
    main()
