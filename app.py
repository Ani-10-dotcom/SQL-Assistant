from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import db
import llm

app = FastAPI(title="SQL Assistant")

INDEX_HTML = Path(__file__).parent / "templates" / "index.html"


class AskRequest(BaseModel):
    scenario: str = Field("", max_length=2000)
    question: str = Field(..., min_length=1, max_length=2000)


@lru_cache
def schema() -> str:
    return db.get_schema()


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML.read_text(encoding="utf-8")


@app.post("/api/ask")
def ask(req: AskRequest):
    try:
        generated = llm.generate_sql(req.scenario, req.question, schema())
    except llm.LLMError as exc:
        return {"sql": "", "explanation": "", "result": {"kind": "error", "error": str(exc)}}

    if not generated["sql"]:
        return {**generated, "result": None}
    return {**generated, "result": db.execute(generated["sql"])}


@app.get("/api/health")
def health():
    """Confirms the database file is bundled and readable."""
    return {"ok": True, "tables_and_views": schema().count("\n") + 1}
