import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from llm_provider import build_openai_compatible_client, resolve_openai_compatible_config

load_dotenv(Path(os.path.dirname(__file__)) / "../.env")


PLANNER_DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "google": "gemini-2.5-flash",
}


def get_client() -> OpenAI:
    client, _ = build_openai_compatible_client(
        layer="planner",
        default_models=PLANNER_DEFAULT_MODELS,
        legacy_env_names_by_provider={
            "groq": ("GROQ_MODEL_NAME", "GROQ_MODEL"),
            "google": ("GOOGLE_MODEL_NAME", "GOOGLE_MODEL", "GEMINI_MODEL"),
        },
    )
    return client


def get_model_name() -> str:
    config = resolve_openai_compatible_config(
        layer="planner",
        default_models=PLANNER_DEFAULT_MODELS,
        legacy_env_names_by_provider={
            "groq": ("GROQ_MODEL_NAME", "GROQ_MODEL"),
            "google": ("GOOGLE_MODEL_NAME", "GOOGLE_MODEL", "GEMINI_MODEL"),
        },
    )
    return config.model
