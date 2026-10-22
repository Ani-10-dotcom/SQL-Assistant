# SQL Assistant

Describe a **Scenario** and ask a **Question** in plain English. The app uses Groq to write a
SQLite query against the Northwind sample database and shows it in the **Query** box.

- `SELECT` queries are run on a read-only connection, and the first 200 rows are shown.
- `INSERT` / `UPDATE` / `DELETE` queries are **never applied**. They run on a throwaway in-memory
  copy only to report how many records would be affected.
- Other statements (`DROP`, `CREATE`, `ALTER`, `PRAGMA`, `ATTACH`...) are shown but not executed.
- `northwind.db` is only ever opened with `mode=ro` and `query_only`, so it cannot change.

## Files

| File | What it does |
| --- | --- |
| `app.py` | FastAPI app: serves the page and the `/api/ask` endpoint |
| `llm.py` | Sends the scenario, question and database schema to Groq |
| `db.py` | Read-only query runner and the "rows affected" dry run |
| `templates/index.html` | The page (Scenario, Question, Query, results) |
| `northwind.db` | Northwind sample data for SQLite ([jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3)) |

## Run on your computer

```bash
pip install -r requirements.txt uvicorn
export GROQ_API_KEY=your-key-here      # Windows PowerShell: $env:GROQ_API_KEY="your-key-here"
uvicorn app:app --reload
```

Open http://127.0.0.1:8000.

## Deploy to Vercel

1. Put this folder in a Git repo and import it at vercel.com/new (or run `vercel` in the folder).
   Vercel detects the FastAPI app in `app.py` automatically.
2. In the project's **Settings → Environment Variables**, add `GROQ_API_KEY`.
3. Optional: set `GROQ_MODEL` to change the model (default `llama-3.3-70b-versatile`).
