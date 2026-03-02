"""Custom exception types for catalyst-ci-test."""


class CatalystCITestError(Exception):
    """Base exception for catalyst-ci-test."""


class GitlabCILocalNotFoundError(CatalystCITestError):
    """Raised when gitlab-ci-local is not installed."""


class PipelineExecutionError(CatalystCITestError):
    """Raised when pipeline execution fails unexpectedly."""


class TestSchemaError(CatalystCITestError):
    """Raised when a YAML test file has schema errors."""
