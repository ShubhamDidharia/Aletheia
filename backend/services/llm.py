"""Gemini wrapper. All LLM calls go through here and return validated Pydantic models."""
import os
import asyncio
import logging
from typing import Type, TypeVar, Optional

from google import genai
from pydantic import BaseModel

log = logging.getLogger("aletheia.llm")

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

T = TypeVar("T", bound=BaseModel)

_client: Optional[genai.Client] = None


class LLMError(RuntimeError):
    """Raised when the LLM is misconfigured or fails after retries."""


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise LLMError(
                "GEMINI_API_KEY is not set. Add it to backend/.env — the "
                "planner and analyst agents cannot run without it."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text or "429" in text


async def generate_structured(prompt: str, schema: Type[T], retries: int = 2) -> T:
    """Call Gemini and parse the response into `schema`. Retries transient errors."""
    client = get_client()
    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
            if not response.text:
                raise LLMError("Gemini returned an empty response.")
            return schema.model_validate_json(response.text)
        except Exception as e:
            # A blown quota won't clear in a few seconds — retrying just delays
            # the error and can burn more of the allowance.
            if _is_quota_error(e):
                raise LLMError(
                    f"Gemini quota exhausted for model '{MODEL}'. The free tier allows "
                    f"a limited number of requests per day, which resets at midnight "
                    f"Pacific. Wait for the reset, enable billing on your Google Cloud "
                    f"project, or set GEMINI_MODEL in backend/.env to a model with "
                    f"remaining quota."
                ) from e

            last_error = e
            log.warning("Gemini call failed (attempt %d/%d): %s", attempt + 1, retries + 1, e)
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))

    raise LLMError(f"Gemini call failed after {retries + 1} attempts: {last_error}")
