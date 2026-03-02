"""Assertion helpers for validating pipeline and job results."""

from __future__ import annotations

import re

from .models import JobStatus, PipelineResult


def assert_pipeline_success(result: PipelineResult) -> None:
    """Assert the entire pipeline succeeded."""
    if not result.success:
        failed = [j.name for j in result.failed_jobs]
        raise AssertionError(
            f"Pipeline failed. Failed jobs: {failed}\n"
            f"Return code: {result.return_code}"
        )


def assert_pipeline_failure(result: PipelineResult) -> None:
    """Assert the pipeline failed (useful for negative tests)."""
    if result.success:
        raise AssertionError("Expected pipeline to fail, but it succeeded")


def assert_job_success(result: PipelineResult, job_name: str) -> None:
    """Assert a specific job succeeded."""
    job = result.get_job(job_name)
    if not job.is_successful:
        raise AssertionError(
            f"Job '{job_name}' failed with status {job.status.value}.\n"
            f"Exit code: {job.exit_code}\n"
            f"Output (last 20 lines):\n{_tail(job.stdout, 20)}"
        )


def assert_job_failure(result: PipelineResult, job_name: str) -> None:
    """Assert a specific job failed."""
    job = result.get_job(job_name)
    if job.is_successful:
        raise AssertionError(
            f"Expected job '{job_name}' to fail, "
            f"but it has status {job.status.value}"
        )


def assert_job_ran(result: PipelineResult, job_name: str) -> None:
    """Assert a job actually executed (was not skipped/pending/manual)."""
    job = result.get_job(job_name)
    if job.status in (JobStatus.SKIPPED, JobStatus.PENDING, JobStatus.MANUAL):
        raise AssertionError(
            f"Job '{job_name}' did not run. Status: {job.status.value}"
        )


def assert_job_skipped(result: PipelineResult, job_name: str) -> None:
    """Assert a job was skipped."""
    job = result.get_job(job_name)
    if job.status != JobStatus.SKIPPED:
        raise AssertionError(
            f"Expected job '{job_name}' to be skipped, "
            f"but it has status {job.status.value}"
        )


def assert_job_output_contains(
    result: PipelineResult,
    job_name: str,
    expected: str,
) -> None:
    """Assert a job's output contains the expected text."""
    job = result.get_job(job_name)
    if expected not in job.stdout:
        raise AssertionError(
            f"Job '{job_name}' output does not contain '{expected}'.\n"
            f"Actual output (last 20 lines):\n{_tail(job.stdout, 20)}"
        )


def assert_job_output_matches(
    result: PipelineResult,
    job_name: str,
    pattern: str,
) -> None:
    """Assert a job's output matches a regex pattern."""
    job = result.get_job(job_name)
    if not re.search(pattern, job.stdout):
        raise AssertionError(
            f"Job '{job_name}' output does not match pattern '{pattern}'.\n"
            f"Actual output (last 20 lines):\n{_tail(job.stdout, 20)}"
        )


def assert_artifact_exists(
    result: PipelineResult,
    job_name: str,
    artifact_path: str,
) -> None:
    """Assert an artifact file exists for a job."""
    job = result.get_job(job_name)
    if not job.artifact_exists(artifact_path):
        raise AssertionError(
            f"Artifact '{artifact_path}' does not exist for job '{job_name}'.\n"
            f"Artifacts dir: {job.artifacts_dir}"
        )


def assert_run_jobs(
    result: PipelineResult,
    expected_jobs: list[str],
) -> None:
    """Assert exactly these jobs ran (order-independent)."""
    actual = sorted(j.name for j in result.run_jobs)
    expected = sorted(expected_jobs)
    if actual != expected:
        raise AssertionError(
            f"Expected jobs {expected} to run, but got {actual}"
        )


def assert_run_jobs_contain(
    result: PipelineResult,
    expected_jobs: list[str],
) -> None:
    """Assert at least these jobs ran."""
    actual = {j.name for j in result.run_jobs}
    missing = set(expected_jobs) - actual
    if missing:
        raise AssertionError(
            f"Expected jobs {list(missing)} to run, but they did not. "
            f"Jobs that ran: {sorted(actual)}"
        )


def _tail(text: str, n: int) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:])
