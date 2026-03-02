"""Parse gitlab-ci-local output and state directory into structured results."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from .models import JobResult, JobStatus, PipelineResult


def safe_docker_string(job_name: str) -> str:
    """Replicate gitlab-ci-local's safeDockerString for log file lookup.

    In gitlab-ci-local, non-word/non-hyphen chars are replaced with
    base64url encoding (without padding).
    """

    def _replace(m: re.Match) -> str:
        return base64.urlsafe_b64encode(m.group(0).encode()).decode().rstrip("=")

    return re.sub(r"[^\w-]+", _replace, job_name)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def parse_list_json(json_output: str) -> list[dict]:
    """Parse the output of `gitlab-ci-local --list-json`."""
    try:
        return json.loads(json_output)
    except json.JSONDecodeError:
        return []


def parse_pipeline_output(
    raw_stdout: str,
    raw_stderr: str,
    return_code: int,
    job_metadata: list[dict],
    project_path: Path,
    state_dir: str = ".gitlab-ci-local",
) -> PipelineResult:
    """Parse gitlab-ci-local execution results into a PipelineResult.

    Strategy:
    1. Start with job metadata from --list-json
    2. Read per-job log files from state dir
    3. Parse the summary report from combined output for status markers
    4. Infer status from exit codes and output patterns
    """
    combined_output = strip_ansi(raw_stdout + raw_stderr)
    state_path = project_path / state_dir

    jobs: list[JobResult] = []

    for meta in job_metadata:
        name = meta["name"]
        safe_name = safe_docker_string(name)
        log_path = state_path / "output" / f"{safe_name}.log"
        artifacts_dir = state_path / "artifacts" / name

        job_log = _read_job_log(log_path)
        status = _infer_job_status(name, combined_output, log_path.exists(), meta)
        exit_code = _extract_exit_code(name, combined_output)

        job = JobResult(
            name=name,
            stage=meta.get("stage", "test"),
            status=status,
            exit_code=exit_code,
            allow_failure=meta.get("allowFailure", False),
            stdout=job_log,
            stderr="",
            when=meta.get("when", "on_success"),
            needs=[n.get("job", "") for n in (meta.get("needs") or [])],
            rules=meta.get("rules"),
            artifacts_dir=artifacts_dir if artifacts_dir.exists() else None,
        )
        jobs.append(job)

    return PipelineResult(
        jobs=jobs,
        success=return_code == 0,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        return_code=return_code,
        project_path=project_path,
    )


def _read_job_log(log_path: Path) -> str:
    if log_path.exists():
        return log_path.read_text(encoding="utf-8", errors="replace")
    return ""


def _infer_job_status(
    job_name: str,
    combined_output: str,
    log_exists: bool,
    meta: dict,
) -> JobStatus:
    """Infer job status from gitlab-ci-local output patterns.

    The CLI prints a summary report with markers:
    - PASS: job succeeded
    - WARN: job failed but allow_failure=true
    - FAIL: job failed
    """
    when = meta.get("when", "on_success")
    if when == "never":
        return JobStatus.SKIPPED
    if when == "manual":
        return JobStatus.MANUAL

    escaped_name = re.escape(job_name)

    if re.search(rf"FAIL\s.*?{escaped_name}", combined_output):
        if meta.get("allowFailure", False):
            return JobStatus.WARNING
        return JobStatus.FAILED

    if re.search(rf"WARN\s.*?{escaped_name}", combined_output):
        return JobStatus.WARNING

    if re.search(rf"PASS\s.*?{escaped_name}", combined_output):
        return JobStatus.SUCCESS

    if log_exists:
        return JobStatus.SUCCESS

    return JobStatus.SKIPPED


def _extract_exit_code(job_name: str, combined_output: str) -> int | None:
    escaped_name = re.escape(job_name)
    match = re.search(
        rf"{escaped_name}.*?(?:FAIL|WARN)\s+(\d+)",
        combined_output,
    )
    if match:
        return int(match.group(1))
    return None
