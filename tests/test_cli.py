"""Tests for the CLI commands."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from catalyst_ci_test.cli import main
from catalyst_ci_test.models import JobResult, JobStatus, PipelineResult


class TestRunCommandOptions:
    def test_run_help_shows_job_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "--job" in result.output
        assert "-j" in result.output

    def test_job_flag_sets_env_var(self, tmp_path):
        """Verify --job sets CATALYST_CI_TEST_JOBS env var."""
        captured_env = {}

        def mock_pytest_main(args):
            captured_env["jobs"] = os.environ.get("CATALYST_CI_TEST_JOBS", "")
            return 0

        # Create a dummy test file so the path exists
        (tmp_path / "dummy.test.yml").write_text(
            'description: "test"\nasserts:\n  - type: success\n'
        )

        runner = CliRunner()
        with patch("catalyst_ci_test.cli.sys.exit"):
            with patch("pytest.main", side_effect=mock_pytest_main):
                result = runner.invoke(
                    main, ["run", str(tmp_path), "-j", "build", "-j", "test"]
                )

        assert captured_env.get("jobs") == "build,test"


class TestLintCommand:
    def test_lint_valid_yaml(self, tmp_path):
        f = tmp_path / "pipeline.test.yml"
        f.write_text(
            'description: "Test"\n'
            "asserts:\n"
            "  - type: success\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["lint", str(tmp_path)])
        assert result.exit_code == 0
        assert "All files valid" in result.output

    def test_lint_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.test.yml"
        f.write_text("not: valid: yaml: [[[")

        runner = CliRunner()
        result = runner.invoke(main, ["lint", str(tmp_path)])
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_lint_no_files(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, ["lint", str(tmp_path)])
        assert result.exit_code == 0
        assert "No test files found" in result.output


class TestDryRunCommand:
    def _make_pipeline_result(self, *, success=True):
        """Create a mock PipelineResult for testing."""
        return PipelineResult(
            jobs=[
                JobResult(
                    name="build",
                    stage="build",
                    status=JobStatus.SUCCESS,
                    exit_code=0,
                    stdout="Building...\nBuild complete!",
                ),
                JobResult(
                    name="test",
                    stage="test",
                    status=JobStatus.SUCCESS if success else JobStatus.FAILED,
                    exit_code=0 if success else 1,
                    stdout="Running tests...\nDone.",
                ),
            ],
            success=success,
            return_code=0 if success else 1,
        )

    def test_dry_run_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["dry-run", "--help"])
        assert result.exit_code == 0
        assert "--job" in result.output
        assert "-j" in result.output
        assert "--variable" in result.output
        assert "-e" in result.output
        assert "--show-output" in result.output
        assert "-o" in result.output
        assert "--file" in result.output
        assert "--force-shell-executor" in result.output
        assert "--timeout" in result.output

    def test_dry_run_success(self, tmp_path):
        """Verify dry-run prints results and exits 0 on success."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")
        mock_result = self._make_pipeline_result(success=True)

        with patch(
            "catalyst_ci_test.runner.run_pipeline", return_value=mock_result
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["dry-run", str(tmp_path)])

        assert result.exit_code == 0
        assert "SUCCESS" in result.output
        assert "build" in result.output
        assert "test" in result.output

    def test_dry_run_failure_exit_code(self, tmp_path):
        """Verify dry-run exits with code 1 when pipeline fails."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: exit 1\n")
        mock_result = self._make_pipeline_result(success=False)

        with patch(
            "catalyst_ci_test.runner.run_pipeline", return_value=mock_result
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["dry-run", str(tmp_path)])

        assert result.exit_code == 1
        assert "FAILED" in result.output

    def test_dry_run_with_variables(self, tmp_path):
        """Verify -e KEY=VALUE variables are parsed and passed."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")
        mock_result = self._make_pipeline_result()
        captured_options = {}

        def mock_run_pipeline(path, options=None):
            captured_options["vars"] = options.variables
            return mock_result

        with patch(
            "catalyst_ci_test.runner.run_pipeline",
            side_effect=mock_run_pipeline,
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["dry-run", str(tmp_path), "-e", "FOO=bar", "-e", "BAZ=qux"],
            )

        assert result.exit_code == 0
        assert captured_options["vars"] == {"FOO": "bar", "BAZ": "qux"}

    def test_dry_run_with_jobs(self, tmp_path):
        """Verify -j flag filters specific jobs."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")
        mock_result = self._make_pipeline_result()
        captured_options = {}

        def mock_run_pipeline(path, options=None):
            captured_options["jobs"] = options.jobs
            return mock_result

        with patch(
            "catalyst_ci_test.runner.run_pipeline",
            side_effect=mock_run_pipeline,
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["dry-run", str(tmp_path), "-j", "build", "-j", "lint"],
            )

        assert result.exit_code == 0
        assert captured_options["jobs"] == ["build", "lint"]

    def test_dry_run_invalid_variable_format(self, tmp_path):
        """Verify invalid variable format gives clear error."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        runner = CliRunner()
        result = runner.invoke(
            main, ["dry-run", str(tmp_path), "-e", "INVALID"]
        )

        assert result.exit_code == 1
        assert "Invalid variable format" in result.output

    def test_dry_run_show_output(self, tmp_path):
        """Verify --show-output prints job stdout."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")
        mock_result = self._make_pipeline_result()

        with patch(
            "catalyst_ci_test.runner.run_pipeline", return_value=mock_result
        ):
            runner = CliRunner()
            result = runner.invoke(
                main, ["dry-run", str(tmp_path), "--show-output"]
            )

        assert result.exit_code == 0
        assert "Build complete!" in result.output
        assert "Running tests..." in result.output

    def test_dry_run_pipeline_exception(self, tmp_path):
        """Verify clean error when pipeline execution fails."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        with patch(
            "catalyst_ci_test.runner.run_pipeline",
            side_effect=Exception("gitlab-ci-local not found"),
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["dry-run", str(tmp_path)])

        assert result.exit_code == 1
        assert "Pipeline execution failed" in result.output


class TestInitCommand:
    def test_init_creates_files(self, tmp_path):
        target = tmp_path / "new-project"

        runner = CliRunner()
        result = runner.invoke(main, ["init", str(target)])
        assert result.exit_code == 0

        assert (target / ".gitlab-ci.yml").exists()
        assert (target / "tests" / "pipeline.test.yml").exists()
        assert (target / "tests" / "test_pipeline.py").exists()
