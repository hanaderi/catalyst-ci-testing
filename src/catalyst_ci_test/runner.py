"""Pipeline execution wrapper around gitlab-ci-local."""

from __future__ import annotations

import glob as glob_mod
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import GitlabCILocalNotFoundError, PipelineExecutionError
from .models import PipelineResult
from .parser import parse_list_json, parse_pipeline_output

logger = logging.getLogger(__name__)


@dataclass
class RunOptions:
    """Options for running a pipeline."""

    variables: dict[str, str] = field(default_factory=dict)
    variables_file: str | None = None
    jobs: list[str] | None = None
    templates: list[str] | None = None
    force_shell_executor: bool = False
    timeout: int = 600
    file: str | None = None
    extra_args: list[str] | None = None
    needs: bool = True


def check_gitlab_ci_local() -> str:
    """Verify gitlab-ci-local is installed and return its path."""
    path = shutil.which("gitlab-ci-local")
    if path is None:
        raise GitlabCILocalNotFoundError(
            "gitlab-ci-local is not installed. "
            "Install it with: npm install -g gitlab-ci-local"
        )
    return path


def _build_command(
    options: RunOptions,
    *,
    list_json: bool = False,
) -> list[str]:
    """Build the gitlab-ci-local command.

    Uses ``--cwd .`` because subprocess is executed with ``cwd=project_path``,
    so gitlab-ci-local always runs from within the project directory.
    """
    cmd = ["gitlab-ci-local", "--cwd", ".", "--no-color"]

    if list_json:
        cmd.append("--list-json")
        return cmd

    if options.force_shell_executor:
        cmd.append("--shell-isolation")

    if options.variables_file:
        cmd.extend(["--variables-file", options.variables_file])

    if options.file:
        cmd.extend(["--file", options.file])

    for key, value in options.variables.items():
        cmd.extend(["--variable", f"{key}={value}"])

    if options.needs:
        cmd.append("--needs")

    if options.extra_args:
        cmd.extend(options.extra_args)

    if options.jobs:
        cmd.extend(options.jobs)

    return cmd


def _copy_templates(patterns: list[str], dest: Path) -> None:
    for pattern in patterns:
        for src_path_str in glob_mod.glob(pattern):
            src = Path(src_path_str)
            target = dest / src.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)


def run_pipeline(
    project_path: str | Path,
    options: RunOptions | None = None,
) -> PipelineResult:
    """Run a GitLab CI pipeline locally and return structured results.

    1. Validates gitlab-ci-local is available
    2. Copies template files if specified
    3. Runs --list-json to get job metadata
    4. Runs the actual pipeline
    5. Parses results from output + state directory
    """
    if options is None:
        options = RunOptions()

    check_gitlab_ci_local()
    project_path = Path(project_path).resolve()

    ci_file = project_path / ".gitlab-ci.yml"
    if not ci_file.exists() and not options.file:
        raise PipelineExecutionError(
            f"No .gitlab-ci.yml found in {project_path}"
        )

    if options.templates:
        _copy_templates(options.templates, project_path)

    # Phase 1: Get job metadata via --list-json
    list_cmd = _build_command(options, list_json=True)
    try:
        list_result = subprocess.run(
            list_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_path),
        )
        if list_result.returncode != 0:
            stderr = list_result.stderr.strip()
            logger.warning(
                "gitlab-ci-local --list-json failed (exit %d): %s",
                list_result.returncode,
                stderr,
            )
            raise PipelineExecutionError(
                f"gitlab-ci-local --list-json failed (exit {list_result.returncode}): "
                f"{stderr}"
            )
        job_metadata = parse_list_json(list_result.stdout)
    except subprocess.TimeoutExpired as e:
        raise PipelineExecutionError(
            "gitlab-ci-local --list-json timed out after 30s"
        ) from e

    # Phase 2: Run the pipeline
    run_cmd = _build_command(options)
    try:
        result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            timeout=options.timeout,
            cwd=str(project_path),
        )
    except subprocess.TimeoutExpired as e:
        raise PipelineExecutionError(
            f"Pipeline timed out after {options.timeout}s"
        ) from e

    # Phase 3: Parse results
    return parse_pipeline_output(
        raw_stdout=result.stdout,
        raw_stderr=result.stderr,
        return_code=result.returncode,
        job_metadata=job_metadata,
        project_path=project_path,
    )
