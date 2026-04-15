from __future__ import annotations

import os

from openai import OpenAI

from .node import LLMClientProtocol


class OpenAICompatibleReviewerClient(LLMClientProtocol):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Reviewer model returned empty content.")

        return content


def build_reviewer_llm_client() -> OpenAICompatibleReviewerClient:
    model = os.environ["REVIEWER_MODEL"]
    api_key = os.environ["GROQ_API_KEY"]
    base_url = os.environ.get("GROQ_BASE_URL")
    temperature = float(os.environ.get("REVIEWER_TEMPERATURE", "0.2"))

    return OpenAICompatibleReviewerClient(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )