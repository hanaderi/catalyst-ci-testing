"""Tests for the output parser module."""

from pathlib import Path

from catalyst_ci_test.parser import (
    parse_list_json,
    parse_pipeline_output,
    safe_docker_string,
    strip_ansi,
)


class TestSafeDockerString:
    def test_simple_name(self):
        assert safe_docker_string("build") == "build"

    def test_name_with_hyphen(self):
        assert safe_docker_string("my-job") == "my-job"

    def test_name_with_underscore(self):
        assert safe_docker_string("my_job") == "my_job"

    def test_name_with_slash(self):
        result = safe_docker_string("deploy/production")
        assert result != "deploy/production"
        assert "/" not in result

    def test_name_with_spaces(self):
        result = safe_docker_string("my job name")
        assert " " not in result

    def test_name_with_colon(self):
        result = safe_docker_string("deploy:staging")
        assert ":" not in result


class TestStripAnsi:
    def test_no_ansi(self):
        assert strip_ansi("hello world") == "hello world"

    def test_with_color(self):
        assert strip_ansi("\x1b[32mgreen\x1b[0m") == "green"

    def test_with_bold(self):
        assert strip_ansi("\x1b[1mbold\x1b[0m") == "bold"

    def test_mixed(self):
        text = "\x1b[31merror\x1b[0m: \x1b[33mwarning\x1b[0m"
        assert strip_ansi(text) == "error: warning"


class TestParseListJson:
    def test_valid_json(self):
        data = '[{"name": "build", "stage": "build"}]'
        result = parse_list_json(data)
        assert len(result) == 1
        assert result[0]["name"] == "build"

    def test_empty_json(self):
        assert parse_list_json("[]") == []

    def test_invalid_json(self):
        assert parse_list_json("not json") == []

    def test_empty_string(self):
        assert parse_list_json("") == []


class TestParsePipelineOutput:
    def test_successful_pipeline(self, tmp_path):
        job_metadata = [
            {"name": "build", "stage": "build", "when": "on_success"},
            {"name": "test", "stage": "test", "when": "on_success"},
        ]

        # Create state dir with log files
        output_dir = tmp_path / ".gitlab-ci-local" / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "build.log").write_text("Building...\nDone")
        (output_dir / "test.log").write_text("Testing...\nPassed")

        result = parse_pipeline_output(
            raw_stdout="",
            raw_stderr="PASS  build\nPASS  test\n",
            return_code=0,
            job_metadata=job_metadata,
            project_path=tmp_path,
        )

        assert result.success is True
        assert len(result.jobs) == 2
        assert result.jobs[0].name == "build"
        assert result.jobs[0].status.value == "success"
        assert result.jobs[1].name == "test"

    def test_failed_pipeline(self, tmp_path):
        job_metadata = [
            {"name": "build", "stage": "build", "when": "on_success"},
        ]

        output_dir = tmp_path / ".gitlab-ci-local" / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "build.log").write_text("Error!")

        result = parse_pipeline_output(
            raw_stdout="",
            raw_stderr="FAIL  build\n",
            return_code=1,
            job_metadata=job_metadata,
            project_path=tmp_path,
        )

        assert result.success is False
        assert result.jobs[0].status.value == "failed"

    def test_skipped_job(self, tmp_path):
        job_metadata = [
            {"name": "deploy", "stage": "deploy", "when": "never"},
        ]

        result = parse_pipeline_output(
            raw_stdout="",
            raw_stderr="",
            return_code=0,
            job_metadata=job_metadata,
            project_path=tmp_path,
        )

        assert result.jobs[0].status.value == "skipped"

    def test_allow_failure_job(self, tmp_path):
        job_metadata = [
            {
                "name": "lint",
                "stage": "test",
                "when": "on_success",
                "allowFailure": True,
            },
        ]

        output_dir = tmp_path / ".gitlab-ci-local" / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "lint.log").write_text("Lint errors")

        result = parse_pipeline_output(
            raw_stdout="",
            raw_stderr="WARN  lint\n",
            return_code=0,
            job_metadata=job_metadata,
            project_path=tmp_path,
        )

        assert result.jobs[0].status.value == "warning"
        assert result.jobs[0].is_successful is True

    def test_job_stdout_from_log(self, tmp_path):
        job_metadata = [
            {"name": "hello", "stage": "test", "when": "on_success"},
        ]

        output_dir = tmp_path / ".gitlab-ci-local" / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "hello.log").write_text("Hello world\n")

        result = parse_pipeline_output(
            raw_stdout="",
            raw_stderr="",
            return_code=0,
            job_metadata=job_metadata,
            project_path=tmp_path,
        )

        assert "Hello world" in result.jobs[0].stdout

    def test_artifacts_dir_exists(self, tmp_path):
        job_metadata = [
            {"name": "build", "stage": "build", "when": "on_success"},
        ]

        output_dir = tmp_path / ".gitlab-ci-local" / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "build.log").write_text("done")

        artifacts_dir = tmp_path / ".gitlab-ci-local" / "artifacts" / "build"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "output.txt").write_text("artifact")

        result = parse_pipeline_output(
            raw_stdout="",
            raw_stderr="",
            return_code=0,
            job_metadata=job_metadata,
            project_path=tmp_path,
        )

        assert result.jobs[0].artifacts_dir is not None
        assert result.jobs[0].artifact_exists("output.txt")
