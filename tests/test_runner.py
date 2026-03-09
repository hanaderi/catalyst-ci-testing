"""Tests for the pipeline runner module."""

import os
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
    _build_env,
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

    def test_uses_resolved_executable_path(self):
        """On Windows, the full resolved path (e.g. .cmd) should be used."""
        cmd = _build_command(
            RunOptions(),
            executable="C:\\Users\\me\\AppData\\Roaming\\npm\\gitlab-ci-local.cmd",
        )
        assert cmd[0] == "C:\\Users\\me\\AppData\\Roaming\\npm\\gitlab-ci-local.cmd"
        assert cmd[1:4] == ["--cwd", ".", "--no-color"]


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


class TestBuildEnv:
    def test_returns_none_on_linux(self):
        """On Linux, _build_env should return None (inherit parent env)."""
        with patch("catalyst_ci_test.runner.sys") as mock_sys:
            mock_sys.platform = "linux"
            assert _build_env() is None

    def test_returns_none_on_darwin(self):
        """On macOS, _build_env should return None."""
        with patch("catalyst_ci_test.runner.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert _build_env() is None

    def test_sets_msys_no_pathconv_on_windows(self):
        """On Windows, _build_env should set MSYS_NO_PATHCONV=1."""
        with patch("catalyst_ci_test.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=True):
                env = _build_env()
                assert env is not None
                assert env["MSYS_NO_PATHCONV"] == "1"

    def test_preserves_existing_env_on_windows(self):
        """On Windows, _build_env should preserve all existing env vars."""
        with patch("catalyst_ci_test.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch.dict(
                "os.environ",
                {"MY_VAR": "hello", "PATH": "/usr/bin"},
                clear=True,
            ):
                env = _build_env()
                assert env["MY_VAR"] == "hello"
                assert env["PATH"] == "/usr/bin"
                assert env["MSYS_NO_PATHCONV"] == "1"

    def test_does_not_mutate_os_environ(self):
        """_build_env should copy the env, not mutate os.environ."""
        with patch("catalyst_ci_test.runner.sys") as mock_sys:
            mock_sys.platform = "win32"
            had_key = "MSYS_NO_PATHCONV" in os.environ
            _build_env()
            if not had_key:
                assert "MSYS_NO_PATHCONV" not in os.environ


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

    def test_subprocess_uses_resolved_executable(self, tmp_path):
        """The resolved path from shutil.which should be used in the command."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        mock_list_result = MagicMock()
        mock_list_result.returncode = 0
        mock_list_result.stdout = (
            '[{"name": "test", "stage": "test", "when": "on_success"}]'
        )
        mock_list_result.stderr = ""

        mock_run_result = MagicMock()
        mock_run_result.returncode = 0
        mock_run_result.stdout = ""
        mock_run_result.stderr = "PASS  test\n"

        resolved = "C:\\Users\\me\\AppData\\Roaming\\npm\\gitlab-ci-local.cmd"
        with patch(
            "catalyst_ci_test.runner.shutil.which",
            return_value=resolved,
        ):
            with patch(
                "catalyst_ci_test.runner.subprocess.run",
                side_effect=[mock_list_result, mock_run_result],
            ) as mock_run:
                run_pipeline(tmp_path)

                # Both subprocess calls should use the resolved executable
                for call in mock_run.call_args_list:
                    cmd = call.args[0]
                    assert cmd[0] == resolved

    def test_subprocess_receives_env_on_windows(self, tmp_path):
        """On Windows, subprocess should receive env with MSYS_NO_PATHCONV."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        mock_list_result = MagicMock()
        mock_list_result.returncode = 0
        mock_list_result.stdout = (
            '[{"name": "test", "stage": "test", "when": "on_success"}]'
        )
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
                with patch("catalyst_ci_test.runner.sys") as mock_sys:
                    mock_sys.platform = "win32"
                    run_pipeline(tmp_path)

                    # Both subprocess calls should have env with MSYS_NO_PATHCONV
                    for call in mock_run.call_args_list:
                        env = call.kwargs.get("env")
                        assert env is not None
                        assert env["MSYS_NO_PATHCONV"] == "1"

    def test_subprocess_receives_no_env_on_linux(self, tmp_path):
        """On Linux, subprocess should receive env=None (inherit parent)."""
        (tmp_path / ".gitlab-ci.yml").write_text("test:\n  script: echo hi\n")

        mock_list_result = MagicMock()
        mock_list_result.returncode = 0
        mock_list_result.stdout = (
            '[{"name": "test", "stage": "test", "when": "on_success"}]'
        )
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
                with patch("catalyst_ci_test.runner.sys") as mock_sys:
                    mock_sys.platform = "linux"
                    run_pipeline(tmp_path)

                    # Both subprocess calls should have env=None
                    for call in mock_run.call_args_list:
                        assert call.kwargs.get("env") is None
