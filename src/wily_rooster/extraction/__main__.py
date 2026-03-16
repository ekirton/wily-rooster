"""CLI entry point for ``python -m wily_rooster.extraction``."""

import logging
import sys
from pathlib import Path

import click

from wily_rooster.extraction.pipeline import run_extraction


@click.command()
@click.option(
    "--target",
    required=True,
    help=(
        'Library targets separated by "+". '
        "Built-in targets: stdlib, mathcomp. "
        "A filesystem path is also accepted."
    ),
)
@click.option(
    "--db",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to the output SQLite index database.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging for extraction (shows raw About output).",
)
def main(target: str, db: Path, verbose: bool) -> None:
    """Extract and index Coq libraries into a SQLite database."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s")
        logging.getLogger("wily_rooster.extraction").setLevel(logging.DEBUG)

    targets = [t.strip() for t in target.split("+") if t.strip()]

    def progress(msg: str) -> None:
        click.echo(msg)

    try:
        report = run_extraction(
            targets=targets,
            db_path=db,
            progress_callback=progress,
        )
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(
        f"Done — indexed {report['declarations_indexed']} declarations "
        f"(Coq {report['coq_version']})"
    )


if __name__ == "__main__":
    main()
