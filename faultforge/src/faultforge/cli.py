"""Command-line interface for FaultForge."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

import click
import yaml

from faultforge import __version__
from faultforge.oracle import Oracle
from faultforge.runner import TrialRunner
from faultforge.search import (
    EXHAUSTIVE_GRID,
    RANDOM_SUBSET_GRID,
    SHUFFLED_GRID,
    SearchConfig,
    Searcher,
    SearchStrategy,
)
from faultforge.trial import BenchmarkConfig, SlowFaultKind, SystemConfig

_STRATEGY_CHOICES: dict[str, SearchStrategy] = {
    "exhaustive": EXHAUSTIVE_GRID,
    "shuffled": SHUFFLED_GRID,
    "random-subset": RANDOM_SUBSET_GRID,
}


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="faultforge")
def main() -> None:
    """FaultForge: symptom-guided fault reproduction orchestrator."""


@main.command("search")
@click.option("--issue-id", default="", help="Issue id stored on emitted trials.")
@click.option(
    "--oracle",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="YAML issue/oracle definition (see Oracle.from_file).",
)
@click.option("--system", default="etcd", help="Target system name.")
@click.option("--benchmark", default="ycsb", help="Benchmark name.")
@click.option("--max-trials", type=int, default=100, show_default=True)
@click.option(
    "--strategy",
    type=click.Choice(tuple(_STRATEGY_CHOICES)),
    default="exhaustive",
    show_default=True,
)
@click.option("--seed", type=int, default=None, help="Strategy RNG seed where applicable.")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Plan trials without executing them.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output results as JSON lines.",
)
@click.option(
    "--nodes",
    multiple=True,
    default=None,
    help="Target nodes (repeatable). Default: leader, follower.",
)
@click.option(
    "--fault-models",
    multiple=True,
    default=None,
    help="Fault models: nw, fs (repeatable). Default: nw, fs.",
)
@click.option(
    "--magnitudes",
    multiple=True,
    type=int,
    default=None,
    help="Delay magnitudes in ms (repeatable). Default: 10, 50, 100, 250, 500.",
)
@click.option(
    "--start-times",
    multiple=True,
    type=int,
    default=None,
    help="Fault start times in seconds (repeatable). Default: 0, 10, 30.",
)
@click.option(
    "--durations",
    multiple=True,
    type=int,
    default=None,
    help="Fault durations in seconds (repeatable). Default: 30, 60.",
)
@click.option(
    "--max-faults-per-trial",
    type=int,
    default=1,
    show_default=True,
    help="Maximum number of simultaneous faults per trial.",
)
def search_cmd(
    issue_id: str,
    oracle: Path | None,
    system: str,
    benchmark: str,
    max_trials: int,
    strategy: str,
    seed: int | None,
    dry_run: bool,
    output_json: bool,
    nodes: tuple[str, ...],
    fault_models: tuple[str, ...],
    magnitudes: tuple[int, ...],
    start_times: tuple[int, ...],
    durations: tuple[int, ...],
    max_faults_per_trial: int,
) -> None:
    """Run the bounded Cartesian search loop."""
    ora: Oracle | None = None
    if oracle is not None:
        ora = Oracle.from_file(oracle)
        issue_id = issue_id or ora.configured_issue_id

    sys_cfg = SystemConfig(name=system)
    bm_cfg = BenchmarkConfig(name=benchmark)

    node_list = list(nodes) if nodes else ["leader", "follower"]
    model_list = cast(
        list["SlowFaultKind"],
        list(fault_models) if fault_models else ["nw", "fs"],
    )
    mag_list = list(magnitudes) if magnitudes else [10, 50, 100, 250, 500]
    start_list = list(start_times) if start_times else [0, 10, 30]
    dur_list = list(durations) if durations else [30, 60]

    cfg = SearchConfig(
        system=sys_cfg,
        benchmark=bm_cfg,
        nodes=node_list,
        fault_models=model_list,
        magnitudes_ms=mag_list,
        start_times_s=start_list,
        durations_s=dur_list,
        max_faults_per_trial=max_faults_per_trial,
        max_trials=max_trials,
        strategy=_STRATEGY_CHOICES[strategy],
        strategy_seed=seed,
        oracle=ora,
    )

    if dry_run:
        trials = cfg.bounded_trials(issue_id=issue_id)
        if output_json:
            for t in trials:
                click.echo(json.dumps(asdict(t)))
        else:
            for t in trials:
                fault_labels = ", ".join(f.info for f in t.faults)
                click.echo(f"{t.trial_id}\t{fault_labels}")
        click.echo(f"{len(trials)} trial(s) planned", err=True)
        return

    results = Searcher(TrialRunner()).run(cfg, issue_id=issue_id)

    if output_json:
        for r in results:
            click.echo(json.dumps(asdict(r)))
    else:
        for r in results:
            click.echo(
                f"{r.trial_index}\t{r.trial.trial_id}\t{r.symptom_score}\t{r.oracle_success}"
            )
    click.echo(f"{len(results)} result(s)", err=True)


@main.command("preflight")
@click.argument("experiment", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--runtime", type=click.Path(dir_okay=False, path_type=Path), default=None)
def preflight_cmd(experiment: Path, runtime: Path | None) -> None:
    """Validate the runtime environment before running an experiment."""
    from faultforge.preflight import Preflight
    from faultforge.runtime import load_runtime

    rt = load_runtime(runtime)
    report = Preflight(rt).run()

    for check in report.checks:
        status = "✓" if check.passed else "✗"
        msg = f"  {status} {check.name}"
        if check.message:
            msg += f": {check.message}"
        click.echo(msg)

    if not report.passed:
        click.echo(
            f"\n{len(report.failed)} check(s) failed. Fix before running experiment.",
            err=True,
        )
        raise SystemExit(1)
    click.echo("\nAll checks passed.", err=True)


@main.command("experiment")
@click.argument("config_file", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--runtime",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Runtime config YAML file.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for results. Default: experiments/<name>.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Plan trials without executing them.",
)
def experiment_cmd(
    config_file: Path,
    runtime: Path | None,
    output_dir: Path | None,
    dry_run: bool,
) -> None:
    """Run a batch experiment from a YAML config file."""
    from faultforge.experiment import Experiment, ExperimentRunner
    from faultforge.runtime import load_runtime

    rt = load_runtime(runtime)
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    exp = Experiment(
        name=raw["name"],
        configs=[],
        output_dir=output_dir or Path("experiments"),
    )

    for entry in raw.get("runs", []):
        ora: Oracle | None = None
        oracle_path = entry.get("oracle")
        issue_id = entry.get("issue_id", "")
        if oracle_path:
            ora = Oracle.from_file(Path(oracle_path))
            issue_id = issue_id or ora.configured_issue_id

        sys_cfg = SystemConfig(name=entry.get("system", "etcd"))
        bm_cfg = BenchmarkConfig(name=entry.get("benchmark", "ycsb"))

        cfg = SearchConfig(
            system=sys_cfg,
            benchmark=bm_cfg,
            nodes=entry.get("nodes", ["leader", "follower"]),
            fault_models=entry.get("fault_models", ["nw", "fs"]),
            magnitudes_ms=entry.get("magnitudes_ms", [10, 50, 100, 250, 500]),
            start_times_s=entry.get("start_times_s", [0, 10, 30]),
            durations_s=entry.get("durations_s", [30, 60]),
            max_faults_per_trial=entry.get("max_faults_per_trial", 1),
            max_trials=entry.get("max_trials", 100),
            strategy=_STRATEGY_CHOICES.get(entry.get("strategy", "exhaustive"), EXHAUSTIVE_GRID),
            strategy_seed=entry.get("seed"),
            oracle=ora,
        )
        exp.add(entry["name"], cfg, issue_id=issue_id)

    if dry_run:
        for name, cfg in exp.configs:
            issue_id = exp.issue_ids.get(name, "")
            trials = cfg.bounded_trials(issue_id=issue_id)
            click.echo(f"[{name}] {len(trials)} trial(s)")
        click.echo(f"{len(exp.configs)} config(s), dry-run complete", err=True)
        return

    results = ExperimentRunner(TrialRunner(rt)).run(exp)
    for r in results:
        status = "SYMPTOM" if r.any_symptom else "no symptom"
        click.echo(f"[{r.name}] {r.top_match.trial.trial_id if r.top_match else 'n/a'} ({status})")
    click.echo(f"{len(results)} config(s) completed", err=True)
