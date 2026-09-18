"""Exception hierarchy for the LLM harness.

Every failure mode the harness can produce is represented here so that
callers (agents, workflows) can catch precisely what they care about
instead of a generic Exception.
"""


class HarnessError(Exception):
    """Base class for all harness-raised errors."""


class SchemaValidationError(HarnessError):
    """Raised when input or output fails pydantic schema validation."""

    def __init__(self, message: str, errors=None):
        super().__init__(message)
        self.errors = errors or []


class RetryableError(HarnessError):
    """Raised internally for errors the retry loop should retry on

    (rate limits / 5xx). Not normally seen by callers directly -- it is
    caught by the retry loop -- but exposed for tests and custom clients.
    """

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class RetryExhaustedError(HarnessError):
    """Raised when MAX_RETRIES is exceeded and the call still fails."""

    def __init__(self, message: str, last_error: Exception = None, attempts: int = 0):
        super().__init__(message)
        self.last_error = last_error
        self.attempts = attempts


class TimeoutFallbackError(HarnessError):
    """Raised when a call times out AND no fallback value was configured.

    If a fallback *was* configured, the harness returns the fallback
    instead of raising -- this exception only fires when there is
    nothing graceful left to do.
    """

    def __init__(self, message: str, timeout: float = None):
        super().__init__(message)
        self.timeout = timeout
