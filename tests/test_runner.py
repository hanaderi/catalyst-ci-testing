"""Tests for the pipeline runner module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from catalyst_ci_test.exceptions import (
    GitlabCILocalNotFoundError,
    PipelineExecutionError,
)
from catalyst_ci_test.runner import (
    RunOptions,
    _build_command,
    check_gitlab_ci_local,
    run_pipeline,
)


class TestBuildCommand:
    def test_basic_command_uses_relative_cwd(self):
        """gitlab-ci-local requires relative paths for --cwd."""
        cmd = _build_command(RunOptions())
        assert cmd[:4] == ["gitlab-ci-local", "--cwd", ".", "--no-color"]

    def test_list_json(self):
        cmd = _build_command(RunOptions(), list_json=True)
        assert "--list-json" in cmd
        assert "--needs" not in cmd  # list-json exits early

    def test_with_variables(self):
        options = RunOptions(variables={"FOO": "bar", "BAZ": "qux"})
        cmd = _build_command(options)
        assert "--variable" in cmd
        assert "FOO=bar" in cmd
        assert "BAZ=qux" in cmd

    def test_with_jobs(self):
        options = RunOptions(jobs=["build", "test"])
        cmd = _build_command(options)
        assert "build" in cmd
        assert "test" in cmd

    def test_with_needs(self):
        options = RunOptions(needs=True)
        cmd = _build_command(options)
        assert "--needs" in cmd

    def test_without_needs(self):
        options = RunOptions(needs=False)
        cmd = _build_command(options)
        assert "--needs" not in cmd

    def test_with_shell_isolation(self):
        options = RunOptions(force_shell_executor=True)
        cmd = _build_command(options)
        assert "--shell-isolation" in cmd

    def test_with_file(self):
        options = RunOptions(file="custom.yml")
        cmd = _build_command(options)
        assert "--file" in cmd
        assert "custom.yml" in cmd

    def test_with_extra_args(self):
        options = RunOptions(extra_args=["--mount", "/tmp:/data"])
        cmd = _build_command(options)
        assert "--mount" in cmd
        assert "/tmp:/data" in cmd


class TestCheckGitlabCiLocal:
    def test_not_installed(self):
        with patch("catalyst_ci_test.runner.shutil.which", return_value=None):
            with pytest.raises(GitlabCILocalNotFoundError):
                check_gitlab_ci_local()

    def test_installed(self):
        with patch(
            "catalyst_ci_test.runner.shutil.which",
            return_value="/usr/bin/gitlab-ci-local",
        ):
            path = check_gitlab_ci_local()
            assert path == "/usr/bin/gitlab-ci-local"


class TestRunPipeline:
    def test_no_ci_file_raises(self, tmp_path):
        with patch(
            "catalyst_ci_test.runner.shutil.which",
            return_value="/usr/bin/gitlab-ci-local",
        ):
            with pytest.raises(PipelineExecutionError, match="No .gitlab-ci.yml"):
                run_pipeline(tmp_path)

    def test_subprocess_called_with_project_as_cwd(self, tmp_path):
        """Verify subprocess is executed FROM the project directory."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        mock_list_result = MagicMock()
        mock_list_result.returncode = 0
        mock_list_result.stdout = '[{"name": "test", "stage": "test", "when": "on_success"}]'
        mock_list_result.stderr = ""

        mock_run_result = MagicMock()
        mock_run_result.returncode = 0
        mock_run_result.stdout = ""
        mock_run_result.stderr = "PASS  test\n"

        with patch(
            "catalyst_ci_test.runner.shutil.which",
            return_value="/usr/bin/gitlab-ci-local",
        ):
            with patch(
                "catalyst_ci_test.runner.subprocess.run",
                side_effect=[mock_list_result, mock_run_result],
            ) as mock_run:
                result = run_pipeline(tmp_path)

                # Both subprocess calls should use cwd=project_path
                for call in mock_run.call_args_list:
                    assert call.kwargs.get("cwd") == str(tmp_path.resolve())

                # Command should use --cwd . (relative)
                first_cmd = mock_run.call_args_list[0].args[0]
                assert first_cmd[2] == "."

                assert result.success

    def test_list_json_failure_raises(self, tmp_path):
        """Verify --list-json failure gives a clear error, not silent empty list."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: some problem"

        with patch(
            "catalyst_ci_test.runner.shutil.which",
            return_value="/usr/bin/gitlab-ci-local",
        ):
            with patch(
                "catalyst_ci_test.runner.subprocess.run",
                return_value=mock_result,
            ):
                with pytest.raises(PipelineExecutionError, match="list-json failed"):
                    run_pipeline(tmp_path)
