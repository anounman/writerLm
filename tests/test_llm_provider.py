from __future__ import annotations

import os
from contextlib import contextmanager

from llm_provider import resolve_llm_provider, resolve_openai_compatible_config


@contextmanager
def _patched_env(updates: dict[str, str | None]):
    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_provider_defaults_to_groq() -> None:
    with _patched_env(
        {
            "LLM_PROVIDER": None,
            "PLANNER_LLM_PROVIDER": None,
            "GROQ_API_KEY": "test-groq-key",
            "GROQ_MODEL_NAME": None,
            "GROQ_MODEL": None,
            "GOOGLE_API_KEY": None,
            "GEMINI_API_KEY": None,
        }
    ):
        config = resolve_openai_compatible_config(
            layer="planner",
            default_models={"groq": "openai/gpt-oss-120b", "google": "gemini-2.5-flash"},
            legacy_env_names=("GROQ_MODEL_NAME", "GROQ_MODEL", "GOOGLE_MODEL_NAME", "GOOGLE_MODEL"),
        )

        assert resolve_llm_provider("planner") == "groq"
        assert config.provider == "groq"
        assert config.api_key == "test-groq-key"
        assert config.base_url == "https://api.groq.com/openai/v1"
        assert config.model == "openai/gpt-oss-120b"


def test_global_google_provider_uses_google_credentials() -> None:
    with _patched_env(
        {
            "LLM_PROVIDER": "google",
            "GOOGLE_API_KEY": "test-google-key",
            "GOOGLE_MODEL": "gemini-custom",
            "GROQ_API_KEY": "unused-groq-key",
        }
    ):
        config = resolve_openai_compatible_config(
            layer="notes",
            default_models={"groq": "llama-3.3-70b-versatile", "google": "gemini-2.5-flash"},
            legacy_env_names=("GROQ_MODEL", "GROQ_MODEL_NAME", "GOOGLE_MODEL", "GOOGLE_MODEL_NAME"),
        )

        assert resolve_llm_provider("notes") == "google"
        assert config.provider == "google"
        assert config.api_key == "test-google-key"
        assert config.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
        assert config.model == "gemini-custom"


def test_layer_specific_provider_override_wins() -> None:
    with _patched_env(
        {
            "LLM_PROVIDER": "groq",
            "WRITER_LLM_PROVIDER": "google",
            "GROQ_API_KEY": "test-groq-key",
            "GOOGLE_API_KEY": "test-google-key",
        }
    ):
        writer_config = resolve_openai_compatible_config(
            layer="writer",
            default_models={"groq": "llama-3.3-70b-versatile", "google": "gemini-2.5-flash"},
            legacy_env_names=("GROQ_MODEL", "GROQ_MODEL_NAME", "GOOGLE_MODEL", "GOOGLE_MODEL_NAME"),
        )
        planner_config = resolve_openai_compatible_config(
            layer="planner",
            default_models={"groq": "openai/gpt-oss-120b", "google": "gemini-2.5-flash"},
            legacy_env_names=("GROQ_MODEL_NAME", "GROQ_MODEL", "GOOGLE_MODEL_NAME", "GOOGLE_MODEL"),
        )

        assert writer_config.provider == "google"
        assert writer_config.api_key == "test-google-key"
        assert planner_config.provider == "groq"
        assert planner_config.api_key == "test-groq-key"
