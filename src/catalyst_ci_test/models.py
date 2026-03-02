"""Data models for pipeline and job results."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    PENDING = "pending"
    MANUAL = "manual"


class JobResult(BaseModel):
    """Result of a single CI/CD job execution."""

    name: str
    stage: str = "test"
    status: JobStatus = JobStatus.PENDING
    exit_code: int | None = None
    allow_failure: bool = False
    stdout: str = ""
    stderr: str = ""
    duration: str | None = None
    artifacts_dir: Path | None = None
    when: str = "on_success"
    needs: list[str] = Field(default_factory=list)
    rules: list[dict] | None = None

    @property
    def is_successful(self) -> bool:
        return self.status in (JobStatus.SUCCESS, JobStatus.WARNING, JobStatus.SKIPPED)

    @property
    def finished(self) -> bool:
        return self.status not in (JobStatus.PENDING, JobStatus.MANUAL)

    def artifact_exists(self, artifact_path: str) -> bool:
        if self.artifacts_dir is None:
            return False
        return (self.artifacts_dir / artifact_path).exists()

    def get_artifact_path(self, artifact_path: str) -> Path | None:
        if self.artifacts_dir and (self.artifacts_dir / artifact_path).exists():
            return self.artifacts_dir / artifact_path
        return None


class PipelineResult(BaseModel):
    """Result of a full pipeline execution."""

    jobs: list[JobResult] = Field(default_factory=list)
    success: bool = False
    raw_stdout: str = ""
    raw_stderr: str = ""
    return_code: int = 0
    project_path: Path = Path(".")

    @property
    def run_jobs(self) -> list[JobResult]:
        return [j for j in self.jobs if j.finished]

    @property
    def failed_jobs(self) -> list[JobResult]:
        return [j for j in self.jobs if j.status == JobStatus.FAILED]

    def find_job(self, name: str) -> JobResult | None:
        return next((j for j in self.jobs if j.name == name), None)

    def get_job(self, name: str) -> JobResult:
        job = self.find_job(name)
        if job is None:
            available = [j.name for j in self.jobs]
            raise KeyError(f"Job '{name}' not found. Available jobs: {available}")
        return job
