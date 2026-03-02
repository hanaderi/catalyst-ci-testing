"""YAML test file schema and validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter


class AssertSuccess(BaseModel):
    type: Literal["success"] = "success"


class AssertFailure(BaseModel):
    type: Literal["failure"] = "failure"


class AssertJobSuccess(BaseModel):
    type: Literal["job_success"] = "job_success"
    job: str


class AssertJobFailure(BaseModel):
    type: Literal["job_failure"] = "job_failure"
    job: str


class AssertJobRan(BaseModel):
    type: Literal["job_ran"] = "job_ran"
    job: str


class AssertJobSkipped(BaseModel):
    type: Literal["job_skipped"] = "job_skipped"
    job: str


class AssertOutputContains(BaseModel):
    type: Literal["output_contains"] = "output_contains"
    job: str
    expected: str


class AssertOutputMatches(BaseModel):
    type: Literal["output_matches"] = "output_matches"
    job: str
    pattern: str


class AssertArtifactExists(BaseModel):
    type: Literal["artifact_exists"] = "artifact_exists"
    job: str
    path: str


class AssertRunJobs(BaseModel):
    type: Literal["run_jobs"] = "run_jobs"
    jobs: list[str]


class AssertExpr(BaseModel):
    """Freeform Python expression assertion (advanced)."""

    type: Literal["expr"] = "expr"
    test: str


AssertItem = (
    AssertSuccess
    | AssertFailure
    | AssertJobSuccess
    | AssertJobFailure
    | AssertJobRan
    | AssertJobSkipped
    | AssertOutputContains
    | AssertOutputMatches
    | AssertArtifactExists
    | AssertRunJobs
    | AssertExpr
)

_assert_adapter = TypeAdapter(AssertItem)


class YamlTestCase(BaseModel):
    """Schema for a single YAML test case."""

    description: str
    project: str = "."
    variables: dict[str, str] = Field(default_factory=dict)
    variables_file: str | None = None
    templates: list[str] | None = None
    force_shell_executor: bool = False
    jobs: list[str] | None = None
    timeout: int = 600
    asserts: list[dict[str, Any]]

    def parse_asserts(self) -> list[AssertItem]:
        return [_assert_adapter.validate_python(a) for a in self.asserts]
