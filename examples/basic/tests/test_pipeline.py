"""Programmatic tests for the basic example pipeline."""

from pathlib import Path

from catalyst_ci_test.assertions import (
    assert_job_output_contains,
    assert_job_success,
    assert_pipeline_success,
    assert_run_jobs,
)

PROJECT = Path(__file__).parent.parent


def test_pipeline_succeeds(pipeline_runner):
    result = pipeline_runner(PROJECT)
    assert_pipeline_success(result)


def test_build_job(pipeline_runner):
    result = pipeline_runner(PROJECT)
    assert_job_success(result, "build")
    assert_job_output_contains(result, "build", "Build complete")


def test_all_expected_jobs_run(pipeline_runner):
    result = pipeline_runner(PROJECT)
    assert_run_jobs(result, ["build", "test"])
