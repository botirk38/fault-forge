"""Command-line interface for FaultForge."""

from __future__ import annotations

from pathlib import Path

import click

from faultforge import __version__
from faultforge.fault_provider.xinda import Xinda
from faultforge.oracle import Oracle
from faultforge.search import (
    EXHAUSTIVE_GRID,
    RANDOM_SUBSET_GRID,
    SHUFFLED_GRID,
    SearchConfig,
    Searcher,
    SearchStrategy,
)

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
@click.option("--issue-id", default="", help="Issue id stored on emitted recipes.")
@click.option(
    "--oracle",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="YAML issue/oracle definition (see Oracle.from_file).",
)
@click.option("--max-trials", type=int, default=100, show_default=True)
@click.option(
    "--strategy",
    type=click.Choice(tuple(_STRATEGY_CHOICES)),
    default="exhaustive",
    show_default=True,
)
@click.option("--seed", type=int, default=None, help="Strategy RNG seed where applicable.")
def search_cmd(
    issue_id: str,
    oracle: Path | None,
    max_trials: int,
    strategy: str,
    seed: int | None,
) -> None:
    """Run the bounded Cartesian search loop via the Xinda provider."""
    ora: Oracle | None = None
    if oracle is not None:
        ora = Oracle.from_file(oracle)
        issue_id = issue_id or ora.configured_issue_id

    cfg = SearchConfig(
        max_trials=max_trials,
        strategy=_STRATEGY_CHOICES[strategy],
        strategy_seed=seed,
        oracle=ora,
    )
    results = Searcher(Xinda()).run(cfg, issue_id=issue_id)

    for row in results:
        click.echo(
            f"{row.trial_index}\t{row.recipe.trial_id}\t"
            f"{row.symptom_score}\t{row.oracle_success}\t{row.trials_run}"
        )
    click.echo(f"{len(results)} result(s)", err=True)
