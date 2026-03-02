# catalyst-ci-test: GitLab CI Template Testing Tool

## Context

We need a Python CLI tool for testing `.gitlab-ci.yml` templates locally (or in Docker). The tool wraps `gitlab-ci-local` as its execution engine and adds a testing/assertion layer on top. This is similar to [gitlab-ci-test](https://gitlab.com/to-be-continuous/tools/gitlab-ci-test) but written in Python with pytest integration.

**Key requirement**: Full support for `include:` directives (local, remote, template, project, component) — handled by `gitlab-ci-local` under the hood.

## Architecture

```
User writes .test.yml or test_*.py
         |
         v
   pytest collects tests
   (via catalyst-ci-test plugin)
         |
         v
   runner.py shells out to gitlab-ci-local
   1. --list-json -> job metadata
   2. run pipeline -> captures output
         |
         v
   parser.py reconstructs results
   (from CLI output + state dir logs)
         |
         v
   assertions.py validates results
```

## Project Structure

```
catalyst-ci-test/
├── pyproject.toml
├── src/catalyst_ci_test/
│   ├── __init__.py
│   ├── cli.py              # Click CLI (run/lint/init subcommands)
│   ├── runner.py            # Wraps gitlab-ci-local subprocess
│   ├── models.py            # Pydantic: JobResult, PipelineResult
│   ├── parser.py            # Parse gitlab-ci-local output + state dir
│   ├── assertions.py        # assert_pipeline_success, assert_job_output_contains, etc.
│   ├── yaml_schema.py       # YAML test file schema (Pydantic)
│   ├── discovery.py         # Find .test.yml and test_*.py files
│   ├── pytest_plugin.py     # pytest fixtures + YAML test collection
│   ├── scaffold.py          # `init` command templates
│   └── exceptions.py        # Custom exceptions
├── tests/
│   ├── conftest.py
│   ├── test_parser.py
│   ├── test_assertions.py
│   ├── test_yaml_schema.py
│   └── fixtures/
│       └── simple-project/
│           └── .gitlab-ci.yml
└── examples/
    ├── basic/
    │   ├── .gitlab-ci.yml
    │   └── tests/
    │       ├── pipeline.test.yml
    │       └── test_pipeline.py
    └── with-templates/
        ├── templates/
        │   └── deploy.yml
        └── tests/
            └── template.test.yml
```

## Implementation Steps

### Step 1: Project scaffolding
- `pyproject.toml` with hatchling build, dependencies (click, pydantic, pyyaml, rich, pytest), CLI entrypoint `catalyst-ci-test`, and pytest11 plugin registration

### Step 2: exceptions.py
- `CatalystCITestError` (base), `GitlabCILocalNotFoundError`, `PipelineExecutionError`, `TestSchemaError`

### Step 3: models.py — Data models
- `JobStatus` enum: success, failed, warning, skipped, pending, manual
- `JobResult` Pydantic model: name, stage, status, exit_code, allow_failure, stdout, stderr, artifacts_dir, duration
- `PipelineResult` Pydantic model: jobs list, success bool, raw_stdout, raw_stderr, return_code, project_path

### Step 4: parser.py — Parse gitlab-ci-local output
- `safe_docker_string()` — replicate gitlab-ci-local's filename encoding for log file lookup
- `strip_ansi()` — remove ANSI color codes
- `parse_list_json()` — parse `--list-json` output
- `parse_pipeline_output()` — reconstruct PipelineResult from state dir + CLI output

### Step 5: runner.py — Pipeline execution
- `check_gitlab_ci_local()` — verify installation
- `RunOptions` dataclass: variables, jobs, templates, force_shell_executor, timeout, file, extra_args
- `run_pipeline(project_path, options)` — main entry point (two-phase: list-json then execute)

### Step 6: assertions.py — Assertion helpers
- `assert_pipeline_success/failure`, `assert_job_success/failure`, `assert_job_ran/skipped`
- `assert_job_output_contains`, `assert_job_output_matches` (regex)
- `assert_artifact_exists`, `assert_run_jobs`, `assert_run_jobs_contain`

### Step 7: yaml_schema.py — YAML test format
- Pydantic models for each assertion type
- `YamlTestCase` model: description, project, variables, templates, jobs, timeout, asserts

### Step 8: discovery.py — Test file discovery
- Discover `**/*.test.yml` and `**/test_*.py` files

### Step 9: pytest_plugin.py — pytest integration
- `pipeline_runner` fixture, YAML test file collection via YamlTestFile/YamlTestItem

### Step 10: cli.py — CLI commands
- `catalyst-ci-test run [path]`, `catalyst-ci-test lint [path]`, `catalyst-ci-test init [path]`

### Step 11: scaffold.py — Init templates

### Step 12: Examples and test fixtures

### Step 13: Unit tests

## Key Technical Details

**Two-phase execution**: Shell out to gitlab-ci-local in two phases:
1. `gitlab-ci-local --list-json` -> structured job metadata
2. `gitlab-ci-local --no-color` -> execute pipeline, read per-job logs from `.gitlab-ci-local/output/`

**safeDockerString**: gitlab-ci-local encodes job names for log filenames by replacing `[^\w-]+` with base64url. Replicated in Python.

**Docker availability**: `--force-shell-executor` option lets tests run without Docker.

## Dependencies

- **click** — CLI framework
- **pydantic v2** — Data models with validation
- **pyyaml** — YAML parsing
- **rich** — Terminal output formatting
- **pytest** — Test runner + plugin hooks
- **gitlab-ci-local** — External prerequisite (npm install -g gitlab-ci-local)

## Verification

1. `pip install -e .` — install in development mode
2. `catalyst-ci-test lint examples/` — validate example test files
3. `catalyst-ci-test run examples/basic/tests/` — run example tests (requires Docker + gitlab-ci-local)
4. `pytest tests/` — run unit tests (mock subprocess, no Docker needed)
5. `catalyst-ci-test init /tmp/test-scaffold` — verify scaffolding
