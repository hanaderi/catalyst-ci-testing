"""pytest plugin for catalyst-ci-test.

Provides:
- pipeline_runner fixture for programmatic tests
- YAML test file collection (.test.yml / .test.yaml)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from .assertions import (
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
)
from .discovery import load_yaml_test_cases
from .models import PipelineResult
from .runner import RunOptions, run_pipeline
from .yaml_schema import (
    AssertArtifactExists,
    AssertExpr,
    AssertFailure,
    AssertJobFailure,
    AssertJobRan,
    AssertJobSkipped,
    AssertJobSuccess,
    AssertOutputContains,
    AssertOutputMatches,
    AssertRunJobs,
    AssertSuccess,
)


def _get_cli_jobs() -> list[str] | None:
    """Read job filter from CATALYST_CI_TEST_JOBS environment variable.

    This is set by the ``catalyst-ci-test run --job`` CLI flag.
    Returns None if not set or empty.
    """
    env_val = os.environ.get("CATALYST_CI_TEST_JOBS", "").strip()
    if not env_val:
        return None
    return [j.strip() for j in env_val.split(",") if j.strip()]


# ---- Fixtures ----


@pytest.fixture
def pipeline_runner():
    """Fixture providing a function to run pipelines.

    Usage::

        def test_my_pipeline(pipeline_runner):
            result = pipeline_runner("path/to/project", variables={"KEY": "val"})
            assert result.success

    The ``--job`` CLI flag is automatically applied unless the test
    explicitly passes its own ``jobs`` parameter.
    """

    def _run(
        project_path: str | Path,
        *,
        variables: dict[str, str] | None = None,
        jobs: list[str] | None = None,
        templates: list[str] | None = None,
        force_shell_executor: bool = False,
        timeout: int = 600,
        **kwargs: Any,
    ) -> PipelineResult:
        # CLI --job flag acts as default; explicit jobs= takes precedence
        effective_jobs = jobs if jobs is not None else _get_cli_jobs()

        options = RunOptions(
            variables=variables or {},
            jobs=effective_jobs,
            templates=templates,
            force_shell_executor=force_shell_executor,
            timeout=timeout,
        )
        return run_pipeline(project_path, options)

    return _run


# ---- YAML Test Collection ----


def pytest_collect_file(
    parent: pytest.Collector,
    file_path: Path,
) -> YamlTestFile | None:
    if file_path.suffix in (".yml", ".yaml") and ".test." in file_path.name:
        return YamlTestFile.from_parent(parent, path=file_path)
    return None


class YamlTestFile(pytest.File):
    """A .test.yml file containing one or more test cases."""

    def collect(self):
        cases = load_yaml_test_cases(self.path)
        for i, (case, _) in enumerate(cases):
            name = case.description or f"test_case_{i}"
            yield YamlTestItem.from_parent(
                self, name=name, test_case=case, test_file=self.path
            )


class YamlTestItem(pytest.Item):
    """A single test case from a YAML file."""

    def __init__(self, name, parent, test_case, test_file, **kwargs):
        super().__init__(name, parent, **kwargs)
        self.test_case = test_case
        self.test_file = test_file

    def runtest(self):
        case = self.test_case
        project_path = (self.test_file.parent / case.project).resolve()

        # CLI --job flag acts as default; explicit jobs in YAML takes precedence
        effective_jobs = case.jobs if case.jobs is not None else _get_cli_jobs()

        options = RunOptions(
            variables=case.variables,
            variables_file=case.variables_file,
            jobs=effective_jobs,
            templates=case.templates,
            force_shell_executor=case.force_shell_executor,
            timeout=case.timeout,
        )

        result = run_pipeline(project_path, options)

        for assert_item in case.parse_asserts():
            _run_assert(result, assert_item)

    def repr_failure(self, excinfo):
        return f"YAML Test Failed: {self.name}\n{excinfo.getrepr()}"

    def reportinfo(self):
        return self.path, None, f"yaml: {self.name}"


def _run_assert(result: PipelineResult, assertion) -> None:
    match assertion:
        case AssertSuccess():
            assert_pipeline_success(result)
        case AssertFailure():
            assert_pipeline_failure(result)
        case AssertJobSuccess(job=job):
            assert_job_success(result, job)
        case AssertJobFailure(job=job):
            assert_job_failure(result, job)
        case AssertJobRan(job=job):
            assert_job_ran(result, job)
        case AssertJobSkipped(job=job):
            assert_job_skipped(result, job)
        case AssertOutputContains(job=job, expected=expected):
            assert_job_output_contains(result, job, expected)
        case AssertOutputMatches(job=job, pattern=pattern):
            assert_job_output_matches(result, job, pattern)
        case AssertArtifactExists(job=job, path=path):
            assert_artifact_exists(result, job, path)
        case AssertRunJobs(jobs=jobs):
            assert_run_jobs(result, jobs)
        case AssertExpr(test=expr):
            ctx = {
                "result": result,
                "jobs": {j.name: j for j in result.jobs},
            }
            if not eval(expr, {"__builtins__": {}}, ctx):  # noqa: S307
                raise AssertionError(f"Expression failed: {expr}")
