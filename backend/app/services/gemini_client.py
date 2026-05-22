import json

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.config import settings

# Prefer models that work on the current free tier (2.0-flash often has limit: 0).
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
]

_client: genai.Client | None = None


class GeminiServiceError(Exception):
    """Raised when the Gemini API cannot complete a request."""


def _get_client() -> genai.Client:
    global _client
    api_key = settings.gemini_api_key.strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Add your Gemini API key to backend/.env and restart the server.")
    if _client is None:
        _client = genai.Client(api_key=api_key)
    return _client


def _messages_to_prompt(messages: list[dict]) -> str:
    parts = []
    for message in messages:
        role = message.get("role", "user").upper()
        parts.append(f"{role}:\n{message['content']}")
    return "\n\n".join(parts)


def _format_client_error(error: genai_errors.ClientError) -> str:
    message = str(error)
    if "429" in message or "RESOURCE_EXHAUSTED" in message:
        return (
            "Gemini quota exceeded for this model. Wait a minute and try again, "
            "or enable billing at https://aistudio.google.com/"
        )
    if "401" in message or "403" in message or "API_KEY_INVALID" in message:
        return "Invalid GEMINI_API_KEY. Create a new key at https://aistudio.google.com/apikey"
    if "503" in message or "UNAVAILABLE" in message:
        return "Gemini is temporarily busy. Wait a few seconds and try again."
    return f"Gemini API error: {message}"


def create_json_completion(messages: list[dict], json_schema: dict | None = None) -> str:
    client = _get_client()
    prompt = _messages_to_prompt(messages)
    if json_schema:
        prompt += (
            "\n\nReturn valid JSON only, with no markdown fences. "
            f"Expected JSON shape:\n{json.dumps(json_schema)}"
        )

    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=8192,
        response_mime_type="application/json",
    )

    last_error: Exception | None = None
    for model in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Gemini returned an empty response")
            return text
        except genai_errors.ClientError as error:
            last_error = GeminiServiceError(_format_client_error(error))
            # Try the next model on quota / availability issues.
            if "429" in str(error) or "503" in str(error) or "404" in str(error):
                continue
            raise last_error from error
        except ValueError:
            raise
        except Exception as error:
            last_error = GeminiServiceError(f"Gemini request failed: {error}")
            continue

    if last_error:
        raise last_error
    raise GeminiServiceError("No Gemini model could complete the request.")
