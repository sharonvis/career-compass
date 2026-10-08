import os

from dotenv import load_dotenv


load_dotenv()


def get_serpapi_api_key() -> str | None:
    """Return the configured SerpAPI key, if one is available."""
    return os.getenv("SERPAPI_API_KEY", "").strip() or None
