from groq import Groq

from app.core.config import settings


client = Groq(api_key=settings.groq_api_key)


def create_json_completion(messages, json_schema):
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=settings.groq_temperature,
        max_tokens=settings.groq_max_tokens,
        response_format={"type": "json_object", "schema": json_schema},
    )
    return response.choices[0].message.content
