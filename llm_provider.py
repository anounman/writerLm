from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from openai import OpenAI


DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

SUPPORTED_PROVIDERS = {"groq", "google"}


@dataclass(frozen=True)
class OpenAICompatibleProviderConfig:
    layer: str
    provider: str
    api_key: str
    base_url: str
    model: str


def _normalize_provider_name(value: str | None, *, default: str = "groq") -> str:
    normalized = (value or default).strip().lower()

    if normalized in {"gemini", "google", "google_ai", "google-ai"}:
        return "google"

    if normalized in SUPPORTED_PROVIDERS:
        return normalized

    supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
    raise ValueError(f"Unsupported LLM provider '{value}'. Supported providers: {supported}.")


def resolve_llm_provider(layer: str, *, default: str = "groq") -> str:
    layer_key = layer.upper()
    return _normalize_provider_name(
        os.getenv(f"{layer_key}_LLM_PROVIDER") or os.getenv("LLM_PROVIDER"),
        default=default,
    )


def _first_non_empty(env_names: Iterable[str]) -> str | None:
    for env_name in env_names:
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()
    return None


def _resolve_api_key(provider: str) -> str:
    if provider == "groq":
        api_key = _first_non_empty(("GROQ_API_KEY",))
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables.")
        return api_key

    api_key = _first_non_empty(("GOOGLE_API_KEY", "GEMINI_API_KEY"))
    if not api_key:
        raise ValueError(
            "Google provider selected, but neither GOOGLE_API_KEY nor GEMINI_API_KEY "
            "was found in environment variables."
        )
    return api_key


def _resolve_base_url(layer: str, provider: str) -> str:
    layer_key = layer.upper()

    if provider == "groq":
        return (
            _first_non_empty((f"{layer_key}_LLM_BASE_URL", "GROQ_BASE_URL"))
            or DEFAULT_GROQ_BASE_URL
        )

    return (
        _first_non_empty(
            (
                f"{layer_key}_LLM_BASE_URL",
                "GOOGLE_BASE_URL",
                "GEMINI_BASE_URL",
            )
        )
        or DEFAULT_GOOGLE_BASE_URL
    )


def _resolve_model(
    layer: str,
    provider: str,
    *,
    default_models: dict[str, str],
    legacy_env_names: Iterable[str] = (),
    legacy_env_names_by_provider: dict[str, Iterable[str]] | None = None,
) -> str:
    layer_key = layer.upper()
    provider_key = provider.upper()
    provider_legacy_env_names = tuple((legacy_env_names_by_provider or {}).get(provider, ()))

    model = _first_non_empty(
        (
            f"{layer_key}_LLM_MODEL",
            f"{layer_key}_MODEL",
            f"{layer_key}_{provider_key}_MODEL",
            f"{layer_key}_{provider_key}_MODEL_NAME",
            *provider_legacy_env_names,
            f"{provider_key}_MODEL_NAME",
            f"{provider_key}_MODEL",
            *legacy_env_names,
            "LLM_MODEL",
        )
    )
    if model:
        return model

    if provider not in default_models:
        raise ValueError(
            f"No default model configured for provider '{provider}' on layer '{layer}'."
        )

    return default_models[provider]


def resolve_openai_compatible_config(
    *,
    layer: str,
    default_models: dict[str, str],
    legacy_env_names: Iterable[str] = (),
    legacy_env_names_by_provider: dict[str, Iterable[str]] | None = None,
    default_provider: str = "groq",
) -> OpenAICompatibleProviderConfig:
    provider = resolve_llm_provider(layer, default=default_provider)

    return OpenAICompatibleProviderConfig(
        layer=layer,
        provider=provider,
        api_key=_resolve_api_key(provider),
        base_url=_resolve_base_url(layer, provider),
        model=_resolve_model(
            layer,
            provider,
            default_models=default_models,
            legacy_env_names=legacy_env_names,
            legacy_env_names_by_provider=legacy_env_names_by_provider,
        ),
    )


def build_openai_compatible_client(
    *,
    layer: str,
    default_models: dict[str, str],
    legacy_env_names: Iterable[str] = (),
    legacy_env_names_by_provider: dict[str, Iterable[str]] | None = None,
    default_provider: str = "groq",
) -> tuple[OpenAI, OpenAICompatibleProviderConfig]:
    config = resolve_openai_compatible_config(
        layer=layer,
        default_models=default_models,
        legacy_env_names=legacy_env_names,
        legacy_env_names_by_provider=legacy_env_names_by_provider,
        default_provider=default_provider,
    )
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
    )
    return client, config
