"""LLM retry wrapper with exponential backoff."""

import random
import time
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import MAX_RETRIES
from app.exceptions import LLMError


def _exponential_backoff_with_jitter(attempt: int, base: float = 1.0, cap: float = 16.0) -> float:
    """Calculate exponential backoff with jitter."""
    delay = min(base * (2 ** attempt), cap)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter


def call_llm(messages: list[Any], llm: ChatGoogleGenerativeAI) -> str:
    """
    Call LLM with exponential backoff retry on rate limit and timeout.

    Args:
        messages: List of LangChain message objects
        llm: Configured ChatGoogleGenerativeAI instance

    Returns:
        LLM response content as string

    Raises:
        LLMError: If all MAX_RETRIES attempts are exhausted
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = llm.invoke(messages)
            return response.content

        except Exception as e:
            error_msg = str(e).lower()
            is_retryable = (
                "rate limit" in error_msg
                or "429" in error_msg
                or "timeout" in error_msg
                or "timed out" in error_msg
            )

            if is_retryable and attempt < MAX_RETRIES - 1:
                delay = _exponential_backoff_with_jitter(attempt)
                time.sleep(delay)
            elif attempt == MAX_RETRIES - 1:
                raise LLMError(f"Gemini LLM call failed after {MAX_RETRIES} attempts: {str(e)}")
            else:
                raise

    raise LLMError(f"Gemini LLM call failed after {MAX_RETRIES} attempts")
