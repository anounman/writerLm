import os 
from anyio import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(os.path.dirname(__file__)) / "../.env")


def get_client() -> OpenAI:
    api_key = os.getenv("GROQ_API_KEY")
    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/v1")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables.")
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

def get_model_name() -> str:
    return os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b")