import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from llm_provider import (
    build_openai_compatible_client,
    get_default_models_for_layer,
    get_legacy_model_env_names_by_provider,
    resolve_openai_compatible_config,
)

load_dotenv(Path(os.path.dirname(__file__)) / "../.env")


PLANNER_DEFAULT_MODELS = get_default_models_for_layer("planner")


def get_client() -> OpenAI:
    client, _ = build_openai_compatible_client(
        layer="planner",
        default_models=PLANNER_DEFAULT_MODELS,
        legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
    )
    return client


def get_model_name() -> str:
    config = resolve_openai_compatible_config(
        layer="planner",
        default_models=PLANNER_DEFAULT_MODELS,
        legacy_env_names_by_provider=get_legacy_model_env_names_by_provider(),
    )
    return config.model
