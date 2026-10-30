"""Print the model names your API key can use for text generation.

Run: python -m backend.llm.list_models
"""
import sys
from typing import Any

from google import genai

from backend.config import ConfigError, get_api_key


def list_generate_models(client: Any) -> list[str]:
    names = [
        m.name.removeprefix("models/")
        for m in client.models.list()
        if "generateContent" in (m.supported_actions or [])
    ]
    return sorted(names)


def main() -> int:
    try:
        client = genai.Client(api_key=get_api_key())
        names = list_generate_models(client)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 1
    except Exception as exc:  # never echo request details, they may include the key
        print(f"Could not list models ({type(exc).__name__}). Check your key and network.")
        return 1
    print("\n".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
