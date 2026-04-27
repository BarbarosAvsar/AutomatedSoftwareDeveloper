"""OpenAI-backed model provider for planning and coding loops."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

from automated_software_developer.agent.providers.rate_limit import (
    RateLimitBackoff,
    RateLimitEvent,
    extract_rate_limit_event,
)

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """LLM provider implementation using the OpenAI Python SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.3-codex",
        temperature: float = 0.1,
        max_output_tokens: int = 8_000,
        seed: int | None = None,
        max_retries: int = 4,
        min_retry_seconds: float = 2.0,
        max_retry_seconds: float = 30.0,
    ) -> None:
        """Initialize provider with API key and model settings."""
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider.")
        self.client = OpenAI(api_key=resolved_api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.seed = seed
        self.backoff = RateLimitBackoff(
            max_retries=max_retries,
            min_delay_seconds=min_retry_seconds,
            max_delay_seconds=max_retry_seconds,
        )
        self.last_rate_limit: RateLimitEvent | None = None

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON from the configured model."""
        last_error: Exception | None = None
        for attempt in range(1, self.backoff.max_retries + 1):
            try:
                raw_text = self._attempt_generation(system_prompt, user_prompt, seed=seed)
                return _parse_json_response(raw_text)
            except RateLimitError as exc:
                last_error = exc
                self.last_rate_limit = extract_rate_limit_event(exc)
                delay = self._resolve_retry_delay(attempt, self.last_rate_limit)
                logger.warning(
                    "OpenAI rate limit hit; retrying in %.2fs (attempt %s/%s).",
                    delay,
                    attempt,
                    self.backoff.max_retries,
                )
                if attempt >= self.backoff.max_retries:
                    raise
                time.sleep(delay)
            except (APIConnectionError, APITimeoutError) as exc:
                last_error = exc
                delay = self.backoff.next_delay(attempt=attempt, retry_after=None)
                logger.warning(
                    "OpenAI connection error; retrying in %.2fs (attempt %s/%s).",
                    delay,
                    attempt,
                    self.backoff.max_retries,
                )
                if attempt >= self.backoff.max_retries:
                    raise
                time.sleep(delay)
            except APIError as exc:
                last_error = exc
                status = getattr(exc, "status_code", None)
                if status == 429:
                    self.last_rate_limit = extract_rate_limit_event(exc)
                    delay = self._resolve_retry_delay(attempt, self.last_rate_limit)
                    logger.warning(
                        "OpenAI rate limit hit; retrying in %.2fs (attempt %s/%s).",
                        delay,
                        attempt,
                        self.backoff.max_retries,
                    )
                    if attempt >= self.backoff.max_retries:
                        raise
                    time.sleep(delay)
                    continue
                raise
        raise RuntimeError("OpenAI retries exhausted.") from last_error

    def _attempt_generation(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> str:
        """Attempt to generate output using Responses API with fallback."""
        try:
            return self._generate_with_responses_api(
                system_prompt,
                user_prompt,
                seed=seed,
            )
        except Exception:
            return self._generate_with_chat_completions_api(
                system_prompt,
                user_prompt,
                seed=seed,
            )

    def _resolve_retry_delay(self, attempt: int, event: RateLimitEvent | None) -> float:
        """Resolve retry delay from rate limit event or backoff policy."""
        retry_after = event.retry_after_seconds if event is not None else None
        return self.backoff.next_delay(attempt=attempt, retry_after=retry_after)

    def _generate_with_responses_api(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> str:
        """Call Responses API and extract text output."""
        resolved_seed = self.seed if seed is None else seed
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        }
        if resolved_seed is not None:
            payload["seed"] = resolved_seed
        response = self.client.responses.create(**payload)  # type: ignore[call-overload]
        extracted = getattr(response, "output_text", None)
        if extracted:
            return str(extracted)
        return _extract_response_text(response)

    def _generate_with_chat_completions_api(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        seed: int | None = None,
    ) -> str:
        """Call Chat Completions API fallback and extract text output."""
        resolved_seed = self.seed if seed is None else seed
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if resolved_seed is not None:
            payload["seed"] = resolved_seed
        response = self.client.chat.completions.create(**payload)  # type: ignore[call-overload]
        message = response.choices[0].message.content
        if message is None:
            raise RuntimeError("Model returned empty message content.")
        return str(message)


def _extract_response_text(response: Any) -> str:
    """Extract text from SDK responses when output_text is unavailable."""
    parts: list[str] = []
    output = getattr(response, "output", None)
    if output is not None:
        for item in output:
            content = getattr(item, "content", None)
            if content is None and isinstance(item, dict):
                content = item.get("content")
            if not content:
                continue
            for segment in content:
                if isinstance(segment, dict):
                    maybe_text = segment.get("text")
                else:
                    maybe_text = getattr(segment, "text", None)
                if maybe_text:
                    parts.append(str(maybe_text))
    if parts:
        return "\n".join(parts)

    # Last-resort fallback to SDK object dump.
    if hasattr(response, "model_dump_json"):
        return str(response.model_dump_json())
    if hasattr(response, "model_dump"):
        return json.dumps(response.model_dump())
    return str(response)


def _parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object from possibly noisy model output."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Model output did not contain JSON.") from None
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Expected top-level JSON object from model.")
    return parsed
