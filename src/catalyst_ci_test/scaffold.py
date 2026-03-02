"""Scaffold a test project with example files."""

from __future__ import annotations

from pathlib import Path

GITLAB_CI_YML = """\
stages:
  - build
  - test

build:
  stage: build
  image: alpine:latest
  script:
    - echo "Building the project..."
    - echo "Build complete"
    - mkdir -p dist
    - echo "artifact content" > dist/output.txt
  artifacts:
    paths:
      - dist/

test:
  stage: test
  image: alpine:latest
  script:
    - echo "Running tests..."
    - echo "All tests passed"
  needs:
    - build
"""

YAML_TEST = """\
---
description: "Pipeline should succeed"
project: ../
asserts:
  - type: success
  - type: job_success
    job: build
  - type: job_success
    job: test
---
description: "Build job should produce output"
project: ../
asserts:
  - type: output_contains
    job: build
    expected: "Build complete"
  - type: run_jobs
    jobs: [build, test]
"""

PYTHON_TEST = """\
from pathlib import Path

from catalyst_ci_test.assertions import (
    assert_job_output_contains,
    assert_job_success,
    assert_pipeline_success,
)

PROJECT = Path(__file__).parent.parent


def test_pipeline_succeeds(pipeline_runner):
    result = pipeline_runner(PROJECT)
    assert_pipeline_success(result)


def test_build_output(pipeline_runner):
    result = pipeline_runner(PROJECT)
    assert_job_success(result, "build")
    assert_job_output_contains(result, "build", "Build complete")


def test_all_jobs_ran(pipeline_runner):
    result = pipeline_runner(PROJECT)
    actual_jobs = sorted(j.name for j in result.run_jobs)
    assert actual_jobs == ["build", "test"]
"""


def create_scaffold(path: Path) -> None:
    """Create a scaffold test project at the given path."""
    path.mkdir(parents=True, exist_ok=True)

    # .gitlab-ci.yml
    (path / ".gitlab-ci.yml").write_text(GITLAB_CI_YML)

    # tests directory
    tests_dir = path / "tests"
    tests_dir.mkdir(exist_ok=True)

    (tests_dir / "pipeline.test.yml").write_text(YAML_TEST)
    (tests_dir / "test_pipeline.py").write_text(PYTHON_TEST)
