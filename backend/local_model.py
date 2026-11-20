"""Client for the local Ollama chat API."""

import json
import math
import os
from http.client import HTTPException as HTTPProtocolError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalModelUnavailable(RuntimeError):
    """Ollama is unreachable or the requested model is unavailable."""


class LocalModelTimeout(RuntimeError):
    """Ollama did not finish in time."""


class LocalModelResponseError(RuntimeError):
    """Ollama returned an invalid or incomplete response."""


def generate_json(messages: list[dict[str, str]], schema: dict) -> tuple[str, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b-q4_K_M")
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    except ValueError as exc:
        raise LocalModelUnavailable("OLLAMA_TIMEOUT_SECONDS must be a positive number.") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise LocalModelUnavailable("OLLAMA_TIMEOUT_SECONDS must be a positive number.")
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps({
            "model": model,
            "messages": messages,
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"num_ctx": 4096, "num_predict": 768, "temperature": 0},
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as exc:
        exc.close()
        if exc.code == 404:
            raise LocalModelUnavailable(f"Ollama model {model} is unavailable. Pull it first.") from exc
        if exc.code == 503:
            raise LocalModelUnavailable("Ollama is temporarily unavailable.") from exc
        raise LocalModelResponseError(f"Ollama returned HTTP {exc.code}.") from exc
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise LocalModelTimeout("Ollama request timed out.") from exc
        raise LocalModelUnavailable("Could not connect to Ollama.") from exc
    except TimeoutError as exc:
        raise LocalModelTimeout("Ollama request timed out.") from exc
    except OSError as exc:
        raise LocalModelUnavailable("Connection to Ollama was lost.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError, HTTPProtocolError) as exc:
        raise LocalModelResponseError("Ollama returned an invalid response.") from exc

    try:
        content = result["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise LocalModelResponseError("Ollama returned no analysis.") from exc
    if result.get("done") is not True or not isinstance(content, str) or not content.strip():
        raise LocalModelResponseError("Ollama returned an incomplete analysis.")
    if result.get("done_reason") == "length":
        raise LocalModelResponseError("Ollama reached the analysis output limit.")
    return model, content
