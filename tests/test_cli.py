"""Tests for the CLI commands."""

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from catalyst_ci_test.cli import main


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


class TestInitCommand:
    def test_init_creates_files(self, tmp_path):
        target = tmp_path / "new-project"

        runner = CliRunner()
        result = runner.invoke(main, ["init", str(target)])
        assert result.exit_code == 0

        assert (target / ".gitlab-ci.yml").exists()
        assert (target / "tests" / "pipeline.test.yml").exists()
        assert (target / "tests" / "test_pipeline.py").exists()
