"""OpenAI-backed model provider for planning and coding loops."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI


class OpenAIProvider:
    """LLM provider implementation using the OpenAI Python SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.3-codex",
        temperature: float = 0.1,
        max_output_tokens: int = 8_000,
    ) -> None:
        """Initialize provider with API key and model settings."""
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider.")
        self.client = OpenAI(api_key=resolved_api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Generate structured JSON from the configured model."""
        try:
            raw_text = self._generate_with_responses_api(system_prompt, user_prompt)
        except Exception:
            raw_text = self._generate_with_chat_completions_api(system_prompt, user_prompt)
        return _parse_json_response(raw_text)

    def _generate_with_responses_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call Responses API and extract text output."""
        response = self.client.responses.create(
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        )
        extracted = getattr(response, "output_text", None)
        if extracted:
            return str(extracted)
        return _extract_response_text(response)

    def _generate_with_chat_completions_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call Chat Completions API fallback and extract text output."""
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_completion_tokens=self.max_output_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
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
