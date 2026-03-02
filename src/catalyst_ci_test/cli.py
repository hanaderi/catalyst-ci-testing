"""CLI entrypoint for catalyst-ci-test."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="catalyst-ci-test")
def main():
    """catalyst-ci-test: Test GitLab CI/CD pipelines locally."""


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--timeout", default=600, help="Timeout per test in seconds")
@click.option(
    "--force-shell-executor",
    is_flag=True,
    help="Force shell executor (no Docker)",
)
@click.option(
    "--job",
    "-j",
    "jobs",
    multiple=True,
    help="Run only specific job(s). Can be repeated: -j build -j test",
)
def run(
    path: str,
    verbose: bool,
    timeout: int,
    force_shell_executor: bool,
    jobs: tuple[str, ...],
):
    """Run tests at PATH (file or directory).

    Discovers .test.yml and test_*.py files and runs them via pytest.
    Use --job/-j to run only specific GitLab CI jobs.
    """
    import pytest as _pytest

    # Pass job filter to pytest plugin via environment variable
    if jobs:
        os.environ["CATALYST_CI_TEST_JOBS"] = ",".join(jobs)

    args = [path]
    if verbose:
        args.append("-v")

    exit_code = _pytest.main(args)
    sys.exit(exit_code)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def lint(path: str):
    """Validate test files at PATH without running them."""
    from .discovery import discover_test_files, load_yaml_test_cases

    test_path = Path(path)
    yaml_files, py_files = discover_test_files(test_path)

    errors = 0
    for yf in yaml_files:
        try:
            cases = load_yaml_test_cases(yf)
            for case, _ in cases:
                case.parse_asserts()
            console.print(f"  [green]OK[/green] {yf}")
        except Exception as e:
            console.print(f"  [red]FAIL[/red] {yf}: {e}")
            errors += 1

    total = len(yaml_files) + len(py_files)
    console.print(
        f"\nValidated {len(yaml_files)} YAML file(s), "
        f"{len(py_files)} Python file(s)"
    )
    if errors:
        console.print(f"[red]{errors} file(s) had errors[/red]")
        sys.exit(1)
    elif total == 0:
        console.print("[yellow]No test files found[/yellow]")
    else:
        console.print("[green]All files valid[/green]")


@main.command()
@click.argument("path", default=".", type=click.Path())
def init(path: str):
    """Scaffold a test project at PATH."""
    from .scaffold import create_scaffold

    create_scaffold(Path(path))
    console.print(f"[green]Created test scaffold at {path}/[/green]")
