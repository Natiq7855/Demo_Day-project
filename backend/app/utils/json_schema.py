QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "text": {"type": "string"},
                "choices": {"type": "array", "items": {"type": "string"}},
                "answer_key": {"type": "array", "items": {"type": "string"}},
                "difficulty": {"type": "string"},
            },
            "required": ["type", "text", "difficulty"],
        },
        "hint": {"type": ["string", "null"]},
        "explanation": {"type": ["string", "null"]},
    },
    "required": ["question"],
}

ROADMAP_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "question_type": {"type": "string"},
                    "difficulty": {"type": "string"},
                    "metadata": {"type": ["object", "null"]},
                },
                "required": ["topic", "question_type", "difficulty"],
            },
        }
    },
    "required": ["items"],
}
