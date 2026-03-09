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


@main.command(name="dry-run")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--timeout", default=600, help="Pipeline timeout in seconds")
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
@click.option(
    "--variable",
    "-e",
    "variables",
    multiple=True,
    help="Set CI variable (KEY=VALUE). Can be repeated: -e FOO=bar -e BAZ=qux",
)
@click.option(
    "--file",
    "-f",
    "ci_file",
    default=None,
    type=click.Path(),
    help="Custom CI config file path (default: .gitlab-ci.yml)",
)
@click.option(
    "--show-output",
    "-o",
    is_flag=True,
    help="Print full stdout for each job",
)
@click.option(
    "--raw",
    "-r",
    is_flag=True,
    help="Print the full raw gitlab-ci-local output",
)
def dry_run(
    path: str,
    timeout: int,
    force_shell_executor: bool,
    jobs: tuple[str, ...],
    variables: tuple[str, ...],
    ci_file: str | None,
    show_output: bool,
    raw: bool,
):
    """Run a pipeline without test assertions and display results.

    PATH should be a project directory containing a .gitlab-ci.yml file.
    This is useful for debugging your CI config before writing tests.
    """
    from .runner import RunOptions, run_pipeline

    # Parse KEY=VALUE variables
    parsed_vars: dict[str, str] = {}
    for var in variables:
        if "=" not in var:
            console.print(
                f"[red]Invalid variable format: {var!r} "
                f"(expected KEY=VALUE)[/red]"
            )
            sys.exit(1)
        key, value = var.split("=", 1)
        parsed_vars[key] = value

    options = RunOptions(
        variables=parsed_vars,
        jobs=list(jobs) if jobs else None,
        force_shell_executor=force_shell_executor,
        timeout=timeout,
        file=ci_file,
    )

    try:
        result = run_pipeline(path, options)
    except Exception as e:
        console.print(f"[red]Pipeline execution failed: {e}[/red]")
        sys.exit(1)

    _print_results(result, show_output=show_output, raw=raw)
    sys.exit(0 if result.success else 1)


def _print_results(
    result, *, show_output: bool = False, raw: bool = False
) -> None:
    """Print a structured summary of pipeline results using Rich."""
    from rich.panel import Panel
    from rich.table import Table

    from .models import JobStatus

    # Raw mode: dump the full gitlab-ci-local output and return
    if raw:
        if result.raw_stdout:
            console.print(
                Panel(
                    result.raw_stdout.rstrip(),
                    title="[bold]gitlab-ci-local stdout[/bold]",
                    expand=True,
                )
            )
        if result.raw_stderr:
            console.print(
                Panel(
                    result.raw_stderr.rstrip(),
                    title="[bold]gitlab-ci-local stderr[/bold]",
                    border_style="red",
                    expand=True,
                )
            )
        return

    # Pipeline status header
    if result.success:
        console.print(
            f"\nPipeline: [bold green]SUCCESS[/bold green] "
            f"(exit code {result.return_code})"
        )
    else:
        console.print(
            f"\nPipeline: [bold red]FAILED[/bold red] "
            f"(exit code {result.return_code})"
        )
    console.print(f"Project:  {result.project_path}\n")

    # Jobs table
    table = Table(show_header=True, header_style="bold")
    table.add_column("", width=2)
    table.add_column("Job")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Exit Code", justify="right")

    status_icons = {
        JobStatus.SUCCESS: "[green]\u2705[/green]",
        JobStatus.FAILED: "[red]\u274c[/red]",
        JobStatus.WARNING: "[yellow]\u26a0\ufe0f[/yellow]",
        JobStatus.SKIPPED: "[dim]\u23ed\ufe0f[/dim]",
        JobStatus.PENDING: "[dim]\u23f3[/dim]",
        JobStatus.MANUAL: "[blue]\u25b6\ufe0f[/blue]",
    }

    status_styles = {
        JobStatus.SUCCESS: "green",
        JobStatus.FAILED: "red",
        JobStatus.WARNING: "yellow",
        JobStatus.SKIPPED: "dim",
        JobStatus.PENDING: "dim",
        JobStatus.MANUAL: "blue",
    }

    passed = 0
    failed = 0
    skipped = 0

    for job in result.jobs:
        icon = status_icons.get(job.status, "")
        style = status_styles.get(job.status, "")
        exit_str = str(job.exit_code) if job.exit_code is not None else "-"

        table.add_row(
            icon,
            f"[{style}]{job.name}[/{style}]",
            job.stage,
            f"[{style}]{job.status.value}[/{style}]",
            exit_str,
        )

        if job.status == JobStatus.SUCCESS:
            passed += 1
        elif job.status == JobStatus.FAILED:
            failed += 1
        elif job.status == JobStatus.SKIPPED:
            skipped += 1

    console.print(table)

    # Summary line
    parts = []
    if passed:
        parts.append(f"[green]Passed: {passed}[/green]")
    if failed:
        parts.append(f"[red]Failed: {failed}[/red]")
    if skipped:
        parts.append(f"[dim]Skipped: {skipped}[/dim]")
    console.print(" | ".join(parts))

    # Job output panels
    if show_output:
        console.print()
        for job in result.jobs:
            if not job.finished:
                continue
            output = job.stdout.strip() if job.stdout else "(no output)"
            style = "red" if job.status == JobStatus.FAILED else "green"
            console.print(
                Panel(
                    output,
                    title=f"[bold]{job.name}[/bold] ({job.status.value})",
                    border_style=style,
                    expand=True,
                )
            )


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
