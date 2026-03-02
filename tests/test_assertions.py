"""Tests for assertion helpers."""

import pytest

from catalyst_ci_test.assertions import (
    assert_artifact_exists,
    assert_job_failure,
    assert_job_output_contains,
    assert_job_output_matches,
    assert_job_ran,
    assert_job_skipped,
    assert_job_success,
    assert_pipeline_failure,
    assert_pipeline_success,
    assert_run_jobs,
    assert_run_jobs_contain,
)
from catalyst_ci_test.models import JobResult, JobStatus, PipelineResult


def _make_result(
    jobs: list[JobResult] | None = None,
    success: bool = True,
) -> PipelineResult:
    return PipelineResult(
        jobs=jobs or [],
        success=success,
        return_code=0 if success else 1,
    )


def _make_job(
    name: str = "test",
    status: JobStatus = JobStatus.SUCCESS,
    stdout: str = "",
    **kwargs,
) -> JobResult:
    return JobResult(name=name, status=status, stdout=stdout, **kwargs)


class TestPipelineAssertions:
    def test_assert_pipeline_success_passes(self):
        result = _make_result(success=True)
        assert_pipeline_success(result)

    def test_assert_pipeline_success_fails(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.FAILED)],
            success=False,
        )
        with pytest.raises(AssertionError, match="Pipeline failed"):
            assert_pipeline_success(result)

    def test_assert_pipeline_failure_passes(self):
        result = _make_result(success=False)
        assert_pipeline_failure(result)

    def test_assert_pipeline_failure_fails(self):
        result = _make_result(success=True)
        with pytest.raises(AssertionError, match="Expected pipeline to fail"):
            assert_pipeline_failure(result)


class TestJobAssertions:
    def test_assert_job_success_passes(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.SUCCESS)]
        )
        assert_job_success(result, "build")

    def test_assert_job_success_with_warning(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.WARNING)]
        )
        assert_job_success(result, "build")

    def test_assert_job_success_fails(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.FAILED)]
        )
        with pytest.raises(AssertionError, match="failed"):
            assert_job_success(result, "build")

    def test_assert_job_failure_passes(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.FAILED)]
        )
        assert_job_failure(result, "build")

    def test_assert_job_failure_fails(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.SUCCESS)]
        )
        with pytest.raises(AssertionError, match="Expected job"):
            assert_job_failure(result, "build")

    def test_assert_job_not_found(self):
        result = _make_result(jobs=[_make_job("build")])
        with pytest.raises(KeyError, match="not found"):
            assert_job_success(result, "nonexistent")


class TestJobRanAssertions:
    def test_assert_job_ran_passes(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.SUCCESS)]
        )
        assert_job_ran(result, "build")

    def test_assert_job_ran_fails_when_skipped(self):
        result = _make_result(
            jobs=[_make_job("deploy", JobStatus.SKIPPED)]
        )
        with pytest.raises(AssertionError, match="did not run"):
            assert_job_ran(result, "deploy")

    def test_assert_job_skipped_passes(self):
        result = _make_result(
            jobs=[_make_job("deploy", JobStatus.SKIPPED)]
        )
        assert_job_skipped(result, "deploy")

    def test_assert_job_skipped_fails(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.SUCCESS)]
        )
        with pytest.raises(AssertionError, match="to be skipped"):
            assert_job_skipped(result, "build")


class TestOutputAssertions:
    def test_assert_output_contains_passes(self):
        result = _make_result(
            jobs=[_make_job("build", stdout="Build complete\nDone")]
        )
        assert_job_output_contains(result, "build", "Build complete")

    def test_assert_output_contains_fails(self):
        result = _make_result(
            jobs=[_make_job("build", stdout="Some output")]
        )
        with pytest.raises(AssertionError, match="does not contain"):
            assert_job_output_contains(result, "build", "Build complete")

    def test_assert_output_matches_passes(self):
        result = _make_result(
            jobs=[_make_job("build", stdout="Version: 1.2.3")]
        )
        assert_job_output_matches(result, "build", r"Version: \d+\.\d+\.\d+")

    def test_assert_output_matches_fails(self):
        result = _make_result(
            jobs=[_make_job("build", stdout="no version")]
        )
        with pytest.raises(AssertionError, match="does not match"):
            assert_job_output_matches(result, "build", r"Version: \d+")


class TestRunJobsAssertions:
    def test_assert_run_jobs_passes(self):
        result = _make_result(
            jobs=[
                _make_job("build", JobStatus.SUCCESS),
                _make_job("test", JobStatus.SUCCESS),
            ]
        )
        assert_run_jobs(result, ["build", "test"])

    def test_assert_run_jobs_order_independent(self):
        result = _make_result(
            jobs=[
                _make_job("test", JobStatus.SUCCESS),
                _make_job("build", JobStatus.SUCCESS),
            ]
        )
        assert_run_jobs(result, ["build", "test"])

    def test_assert_run_jobs_fails(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.SUCCESS)]
        )
        with pytest.raises(AssertionError, match="Expected jobs"):
            assert_run_jobs(result, ["build", "test"])

    def test_assert_run_jobs_contain_passes(self):
        result = _make_result(
            jobs=[
                _make_job("build", JobStatus.SUCCESS),
                _make_job("test", JobStatus.SUCCESS),
                _make_job("deploy", JobStatus.SUCCESS),
            ]
        )
        assert_run_jobs_contain(result, ["build", "test"])

    def test_assert_run_jobs_contain_fails(self):
        result = _make_result(
            jobs=[_make_job("build", JobStatus.SUCCESS)]
        )
        with pytest.raises(AssertionError, match="Expected jobs"):
            assert_run_jobs_contain(result, ["build", "test"])
