"""Custom exception classes for the Travel Planner."""


class LLMError(RuntimeError):
    """Raised when OpenAI LLM calls fail after exhausting retries."""

    pass


class SearchError(RuntimeError):
    """Raised when Tavily search calls fail after exhausting retries."""

    pass


class ConstraintExtractionError(ValueError):
    """Raised when Coordinator cannot extract valid TravelConstraints from query."""

    def __init__(self, message: str, missing_fields: list[str] = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []
