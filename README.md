# catalyst-ci-test

Test your GitLab CI/CD pipelines and templates locally before pushing. Wraps [gitlab-ci-local](https://github.com/firecow/gitlab-ci-local) with a structured testing layer, supporting both declarative YAML tests and programmatic Python tests via pytest.

## Prerequisites

| Dependency | Version | Install |
|---|---|---|
| Python | >= 3.10 | [python.org](https://www.python.org/) |
| Node.js | >= 18 | [nodejs.org](https://nodejs.org/) |
| gitlab-ci-local | >= 4.52 | `npm install -g gitlab-ci-local` |
| Docker | latest | [docker.com](https://www.docker.com/) |

> **Note**: Docker must be running for pipeline execution. Use `--force-shell-executor` to run without Docker (jobs execute in a local shell instead).

## Windows Support

catalyst-ci-test works on Windows under Git Bash. The tool automatically sets
`MSYS_NO_PATHCONV=1` in the subprocess environment to prevent MSYS path
conversion issues that break `rsync` and `/bin/bash` inside gitlab-ci-local.

### Windows Prerequisites

| Dependency | Notes |
|---|---|
| [Git for Windows](https://git-scm.com/) | Provides Git Bash |
| [Node.js](https://nodejs.org/) | Native Windows build |
| [Docker Desktop](https://www.docker.com/) | Must be running |
| [Python >= 3.10](https://www.python.org/) | Windows installer |

### Option 1: Docker (Recommended)

Run catalyst-ci-test in a container — no local Node.js, rsync, or bash needed.

```bash
# Build the image
docker build -t catalyst-ci-test .

# Run interactively — mount your project and the Docker socket
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v %cd%:/workspace \
  catalyst-ci-test

# Inside the container, all commands work:
catalyst-ci-test dry-run . -o
catalyst-ci-test run tests/
```

> **Note**: Mount the Docker socket (`-v /var/run/docker.sock:...`) so
> gitlab-ci-local can start Docker containers for your CI jobs. On Windows
> use `-v //var/run/docker.sock:/var/run/docker.sock` or run Docker Desktop
> with the "Expose daemon" setting enabled.

### Option 2: WSL

Alternatively, run natively inside
[WSL (Windows Subsystem for Linux)](https://learn.microsoft.com/en-us/windows/wsl/).

```bash
# Inside WSL (Ubuntu)
sudo apt update && sudo apt install -y python3 python3-pip nodejs npm docker.io
pip install catalyst-ci-test
npm install -g gitlab-ci-local
```

## Installation

```bash
# From source (editable / development mode)
git clone <repo-url>
cd catalyst-ci-test
pip install -e ".[dev]"

# Verify
catalyst-ci-test --version
```

## Quick Start

```bash
# 1. Scaffold a test project
catalyst-ci-test init my-tests

# 2. Inspect what was generated
ls my-tests/
#   .gitlab-ci.yml
#   tests/pipeline.test.yml
#   tests/test_pipeline.py

# 3. Run all tests
catalyst-ci-test run my-tests/tests/

# 4. Run a specific job only
catalyst-ci-test run my-tests/tests/ --job build
```

## CLI Reference

### `catalyst-ci-test run [PATH]`

Run test files at PATH (file or directory). Discovers `*.test.yml` and `test_*.py` files automatically.

| Option | Short | Description |
|---|---|---|
| `--verbose` | `-v` | Verbose pytest output |
| `--timeout N` | | Timeout per test in seconds (default: 600) |
| `--force-shell-executor` | | Run jobs in local shell instead of Docker |
| `--job NAME` | `-j` | Run only specific job(s). Repeatable: `-j build -j test` |

```bash
# Run all tests in a directory
catalyst-ci-test run tests/

# Run a single test file
catalyst-ci-test run tests/pipeline.test.yml

# Run only the "build" job across all tests
catalyst-ci-test run tests/ -j build

# Run without Docker
catalyst-ci-test run tests/ --force-shell-executor -v
```

### `catalyst-ci-test dry-run [PATH]`

Run a pipeline directly and display results **without** executing any test assertions. Useful for debugging your `.gitlab-ci.yml` before writing tests.

| Option | Short | Description |
|---|---|---|
| `--job NAME` | `-j` | Run only specific job(s). Repeatable: `-j build -j test` |
| `--variable KEY=VALUE` | `-e` | Set CI variable. Repeatable: `-e FOO=bar -e BAZ=qux` |
| `--file PATH` | `-f` | Custom CI config file (default: `.gitlab-ci.yml`) |
| `--timeout N` | | Pipeline timeout in seconds (default: 600) |
| `--force-shell-executor` | | Run jobs in local shell instead of Docker |
| `--show-output` | `-o` | Print full stdout for each job |
| `--raw` | `-r` | Print the full raw gitlab-ci-local output |

```bash
# Run a pipeline and see job statuses
catalyst-ci-test dry-run path/to/project/

# Run with full job output
catalyst-ci-test dry-run path/to/project/ -o

# Print the full raw CI output (useful for debugging)
catalyst-ci-test dry-run path/to/project/ -r

# Run only the build job
catalyst-ci-test dry-run path/to/project/ -j build

# Pass CI variables
catalyst-ci-test dry-run path/to/project/ -e CI_COMMIT_BRANCH=main -e ENV=prod

# Use without Docker
catalyst-ci-test dry-run path/to/project/ --force-shell-executor -o
```

### `catalyst-ci-test lint [PATH]`

Validate test file schemas without executing pipelines.

```bash
catalyst-ci-test lint tests/
```

### `catalyst-ci-test init [PATH]`

Scaffold a new test project with example `.gitlab-ci.yml` and test files.

```bash
catalyst-ci-test init my-project
```

## Writing Tests

### YAML Declarative Tests

Create files with the `.test.yml` or `.test.yaml` extension. Multiple test cases can be in one file, separated by `---`.

```yaml
---
description: "Pipeline should succeed"
project: ../            # path to directory containing .gitlab-ci.yml
variables:
  CI_COMMIT_BRANCH: main
asserts:
  - type: success
  - type: job_success
    job: build
  - type: output_contains
    job: build
    expected: "Build complete"
---
description: "Pipeline should fail without required variable"
project: ../
variables: {}
asserts:
  - type: failure
```

#### YAML Test Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `description` | string | *required* | Test case name (shown in output) |
| `project` | string | `"."` | Path to project dir (relative to test file) |
| `variables` | map | `{}` | CI/CD variables to inject |
| `variables_file` | string | `null` | Path to variables file |
| `templates` | list | `null` | Glob patterns for template files to copy |
| `jobs` | list | `null` | Run only specific job(s) |
| `force_shell_executor` | bool | `false` | Use shell instead of Docker |
| `timeout` | int | `600` | Timeout in seconds |
| `asserts` | list | *required* | List of assertions to check |

#### Assertion Types

| Type | Fields | Description |
|---|---|---|
| `success` | | Pipeline exited successfully |
| `failure` | | Pipeline failed (for negative tests) |
| `job_success` | `job` | Specific job succeeded |
| `job_failure` | `job` | Specific job failed |
| `job_ran` | `job` | Job executed (was not skipped) |
| `job_skipped` | `job` | Job was skipped |
| `output_contains` | `job`, `expected` | Job stdout contains text |
| `output_matches` | `job`, `pattern` | Job stdout matches regex |
| `artifact_exists` | `job`, `path` | Artifact file exists |
| `run_jobs` | `jobs` | Exactly these jobs ran |
| `expr` | `test` | Python expression evaluates to truthy |

**Examples:**

```yaml
asserts:
  # Pipeline-level
  - type: success
  - type: failure

  # Job-level
  - type: job_success
    job: build
  - type: job_failure
    job: lint

  # Output
  - type: output_contains
    job: build
    expected: "Compiled successfully"
  - type: output_matches
    job: test
    pattern: "\\d+ tests passed"

  # Artifacts
  - type: artifact_exists
    job: build
    path: dist/app.js

  # Job list
  - type: run_jobs
    jobs: [lint, build, test]

  # Advanced: Python expression
  - type: expr
    test: "len(result.run_jobs) >= 2"
```

### Programmatic Python Tests

Write standard pytest test files using the `pipeline_runner` fixture (auto-registered via plugin).

```python
from pathlib import Path
from catalyst_ci_test.assertions import (
    assert_pipeline_success,
    assert_job_success,
    assert_job_output_contains,
    assert_artifact_exists,
    assert_run_jobs,
)

PROJECT = Path(__file__).parent.parent  # directory with .gitlab-ci.yml


def test_pipeline_succeeds(pipeline_runner):
    result = pipeline_runner(PROJECT)
    assert_pipeline_success(result)


def test_build_output(pipeline_runner):
    result = pipeline_runner(PROJECT, variables={"ENV": "prod"})
    assert_job_success(result, "build")
    assert_job_output_contains(result, "build", "Build complete")


def test_specific_jobs(pipeline_runner):
    result = pipeline_runner(PROJECT, jobs=["lint", "build"])
    assert_run_jobs(result, ["lint", "build"])


def test_with_shell_executor(pipeline_runner):
    result = pipeline_runner(PROJECT, force_shell_executor=True)
    assert result.success
```

#### `pipeline_runner` Fixture Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `project_path` | `str \| Path` | *required* | Directory with `.gitlab-ci.yml` |
| `variables` | `dict` | `None` | CI/CD variables to inject |
| `jobs` | `list[str]` | `None` | Run only specific job(s) |
| `templates` | `list[str]` | `None` | Glob patterns for templates to copy |
| `force_shell_executor` | `bool` | `False` | Use shell instead of Docker |
| `timeout` | `int` | `600` | Timeout in seconds |

#### Available Assertion Functions

```python
from catalyst_ci_test.assertions import (
    assert_pipeline_success,      # pipeline passed
    assert_pipeline_failure,      # pipeline failed
    assert_job_success,           # specific job passed
    assert_job_failure,           # specific job failed
    assert_job_ran,               # job was not skipped
    assert_job_skipped,           # job was skipped
    assert_job_output_contains,   # job stdout contains text
    assert_job_output_matches,    # job stdout matches regex
    assert_artifact_exists,       # artifact file exists
    assert_run_jobs,              # exactly these jobs ran
    assert_run_jobs_contain,      # at least these jobs ran
)
```

#### Working with Results Directly

```python
def test_manual_inspection(pipeline_runner):
    result = pipeline_runner("path/to/project")

    # Access jobs
    build = result.get_job("build")   # raises KeyError if not found
    build = result.find_job("build")  # returns None if not found

    # Job properties
    assert build.is_successful
    assert build.status.value == "success"
    print(build.stdout)
    print(build.exit_code)

    # Artifacts
    assert build.artifact_exists("dist/app.js")
    path = build.get_artifact_path("dist/app.js")

    # Pipeline-level
    assert result.success
    assert len(result.run_jobs) == 3
    assert len(result.failed_jobs) == 0
```

## Python Dependencies

| Package | Version | Purpose |
|---|---|---|
| click | >= 8.1 | CLI framework |
| pydantic | >= 2.0 | Data models and validation |
| pyyaml | >= 6.0 | YAML parsing |
| rich | >= 13.0 | Terminal output formatting |
| pytest | >= 8.0 | Test runner and plugin system |

### Dev Dependencies

| Package | Purpose |
|---|---|
| pytest-cov | Code coverage |
| ruff | Linting and formatting |
| mypy | Type checking |

## Project Structure

```
src/catalyst_ci_test/
    __init__.py          # Package version
    cli.py               # Click CLI (run/lint/init)
    runner.py            # Wraps gitlab-ci-local subprocess
    models.py            # JobResult, PipelineResult data models
    parser.py            # Parse gitlab-ci-local output
    assertions.py        # Assertion helper functions
    yaml_schema.py       # YAML test file schema
    discovery.py         # Test file discovery
    pytest_plugin.py     # pytest fixtures + YAML collection
    scaffold.py          # init command templates
    exceptions.py        # Custom exceptions
```

## How It Works

1. **Test discovery**: pytest finds `*.test.yml` and `test_*.py` files
2. **Pipeline execution**: For each test, `gitlab-ci-local` runs the `.gitlab-ci.yml` in Docker containers
3. **Result parsing**: Job output is captured from `gitlab-ci-local`'s state directory (`.gitlab-ci-local/output/`)
4. **Assertions**: Results are validated against declared expectations

The tool uses a two-phase execution model:
- **Phase 1**: `gitlab-ci-local --list-json` to discover job metadata
- **Phase 2**: `gitlab-ci-local` to run the pipeline, then read per-job logs

## Troubleshooting

**"gitlab-ci-local is not installed"**
```bash
npm install -g gitlab-ci-local
```

**Docker errors**
Make sure Docker Desktop is running. Alternatively, use `--force-shell-executor` to skip Docker.

**Timeouts**
Increase the timeout with `--timeout 1200` or set `timeout: 1200` in your YAML test.

**Include resolution failures**
All GitLab `include:` types (local, remote, template, project, component) are handled by `gitlab-ci-local`. Check that remote URLs are accessible and local paths are correct relative to the project directory.

**Windows: rsync `/dev/fd/` or `exclude file` errors**
gitlab-ci-local uses bash process substitution (`<(...)`) in its rsync command
to exclude untracked files. This creates `/dev/fd/` file descriptors which do
not exist on native Windows. This is a fundamental gitlab-ci-local limitation,
not a catalyst-ci-test bug. Two solutions:

1. **Use WSL** (recommended) — run everything inside Windows Subsystem for
   Linux where bash, rsync, and `/dev/fd/` work natively.
2. **Use `--force-shell-executor`** — skips Docker and the rsync step entirely.
   Jobs run in a local shell instead:
   ```bash
   catalyst-ci-test dry-run path/to/project/ --force-shell-executor -o
   ```

**Windows: rsync path conversion errors**
catalyst-ci-test sets `MSYS_NO_PATHCONV=1` automatically. If you still see path
errors, ensure you are running from Git Bash (not PowerShell or CMD) and that
your Python is the native Windows build, not a Cygwin or MSYS Python.

**Windows: `/bin/bash` not found**
This usually indicates `MSYS_NO_PATHCONV` is not taking effect. Ensure you have
the latest version of catalyst-ci-test. As a workaround, use WSL instead.
