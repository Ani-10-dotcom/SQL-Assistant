"""Turns a scenario + question into a single SQLite query using Groq."""

import json
import os

from groq import Groq

DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an expert SQL assistant for a SQLite copy of the Northwind database.

Rules:
- Write exactly ONE SQLite statement that answers the user's question.
- Use only the tables, views and columns listed in the schema below. Never invent names.
- Quote names that contain spaces with square brackets, e.g. [Order Details].
- If the user asks to insert, update or delete data, write that statement anyway; the app
  will not save it, it only reports how many rows would be affected.
- If the question cannot be answered from this schema, or is not about this database,
  return an empty "sql" and explain why in "explanation". Do not guess.

Reply with JSON only, in this shape:
{"sql": "<the query, or empty>", "explanation": "<one or two plain sentences on what the query does>"}

Schema:
"""


class LLMError(Exception):
    pass


def generate_sql(scenario: str, question: str, schema: str) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LLMError("GROQ_API_KEY is not set. Add your Groq API key as an environment variable.")

    client = Groq(api_key=api_key)
    user_message = f"Scenario: {scenario.strip() or '(none given)'}\nQuestion: {question.strip()}"
    try:
        response = client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", DEFAULT_MODEL),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + schema},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise LLMError(f"Groq request failed: {exc}") from exc

    try:
        data = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMError("The model did not return valid JSON.") from exc

    return {
        "sql": str(data.get("sql") or "").strip(),
        "explanation": str(data.get("explanation") or "").strip(),
    }
