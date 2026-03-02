"""Tests for YAML test schema validation."""

import pytest

from catalyst_ci_test.yaml_schema import (
    AssertExpr,
    AssertFailure,
    AssertJobSuccess,
    AssertOutputContains,
    AssertRunJobs,
    AssertSuccess,
    YamlTestCase,
)


class TestYamlTestCase:
    def test_minimal(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "success"}],
        )
        assert case.description == "test"
        assert case.project == "."
        assert case.variables == {}
        assert case.timeout == 600

    def test_full(self):
        case = YamlTestCase(
            description="full test",
            project="../my-project",
            variables={"KEY": "value"},
            force_shell_executor=True,
            jobs=["build"],
            timeout=120,
            asserts=[
                {"type": "success"},
                {"type": "job_success", "job": "build"},
            ],
        )
        assert case.project == "../my-project"
        assert case.variables == {"KEY": "value"}
        assert case.force_shell_executor is True
        assert case.jobs == ["build"]
        assert case.timeout == 120


class TestParseAsserts:
    def test_success(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "success"}],
        )
        parsed = case.parse_asserts()
        assert len(parsed) == 1
        assert isinstance(parsed[0], AssertSuccess)

    def test_failure(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "failure"}],
        )
        parsed = case.parse_asserts()
        assert isinstance(parsed[0], AssertFailure)

    def test_job_success(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "job_success", "job": "build"}],
        )
        parsed = case.parse_asserts()
        assert isinstance(parsed[0], AssertJobSuccess)
        assert parsed[0].job == "build"

    def test_output_contains(self):
        case = YamlTestCase(
            description="test",
            asserts=[
                {"type": "output_contains", "job": "build", "expected": "done"}
            ],
        )
        parsed = case.parse_asserts()
        assert isinstance(parsed[0], AssertOutputContains)
        assert parsed[0].job == "build"
        assert parsed[0].expected == "done"

    def test_run_jobs(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "run_jobs", "jobs": ["build", "test"]}],
        )
        parsed = case.parse_asserts()
        assert isinstance(parsed[0], AssertRunJobs)
        assert parsed[0].jobs == ["build", "test"]

    def test_expr(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "expr", "test": "result.success"}],
        )
        parsed = case.parse_asserts()
        assert isinstance(parsed[0], AssertExpr)
        assert parsed[0].test == "result.success"

    def test_multiple_asserts(self):
        case = YamlTestCase(
            description="test",
            asserts=[
                {"type": "success"},
                {"type": "job_success", "job": "build"},
                {"type": "output_contains", "job": "build", "expected": "ok"},
            ],
        )
        parsed = case.parse_asserts()
        assert len(parsed) == 3

    def test_invalid_type_raises(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "nonexistent"}],
        )
        with pytest.raises(Exception):
            case.parse_asserts()

    def test_missing_required_field_raises(self):
        case = YamlTestCase(
            description="test",
            asserts=[{"type": "job_success"}],  # missing 'job'
        )
        with pytest.raises(Exception):
            case.parse_asserts()
