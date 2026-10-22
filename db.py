"""Read-only access to the Northwind SQLite database.

The real database file is only ever opened with mode=ro. Statements that
would change data (INSERT/UPDATE/DELETE/REPLACE) are run on a throwaway
in-memory copy, purely to count how many rows they would affect.
"""

import re
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "northwind.db"
MAX_ROWS = 200
TIMEOUT_SECONDS = 10

READ_KEYWORDS = {"SELECT", "WITH", "VALUES"}
WRITE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "REPLACE"}

# Never allow these, even on the in-memory copy.
_BLOCKED_ACTIONS = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}


def _authorizer(action, *_):
    return sqlite3.SQLITE_DENY if action in _BLOCKED_ACTIONS else sqlite3.SQLITE_OK


def _open_readonly(restricted: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    if restricted:
        conn.set_authorizer(_authorizer)
    return conn


def _add_timeout(conn: sqlite3.Connection) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)


def get_schema() -> str:
    """Describe every table and view so the model only uses names that exist."""
    # Our own fixed queries only, so PRAGMA table_info is allowed here.
    conn = _open_readonly(restricted=False)
    try:
        lines = []
        objects = conn.execute(
            "SELECT type, name FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        for kind, name in objects:
            cols = conn.execute(f'SELECT name, type FROM pragma_table_info("{name}")').fetchall()
            col_text = ", ".join(f"{c} {t}".strip() for c, t in cols)
            lines.append(f"{kind.upper()} [{name}] ({col_text})")
        return "\n".join(lines)
    finally:
        conn.close()


def _first_keyword(sql: str) -> str:
    # Drop leading comments and whitespace, then take the first word.
    stripped = re.sub(r"^(\s+|--[^\n]*\n?|/\*.*?\*/)+", "", sql, flags=re.S)
    match = re.match(r"[A-Za-z]+", stripped)
    return match.group(0).upper() if match else ""


def _display_value(value):
    # BLOB columns (e.g. Employees.Photo) can't be sent as JSON text.
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<binary data, {len(value):,} bytes>"
    return value


def _run_read(sql: str) -> dict:
    conn = _open_readonly()
    try:
        _add_timeout(conn)
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        return {
            "kind": "read",
            "columns": columns,
            "rows": [[_display_value(v) for v in r] for r in rows[:MAX_ROWS]],
            "truncated": truncated,
        }
    finally:
        conn.close()


def _dry_run_write(sql: str) -> dict:
    source = _open_readonly()
    scratch = sqlite3.connect(":memory:")
    try:
        source.backup(scratch)
        scratch.set_authorizer(_authorizer)
        _add_timeout(scratch)
        scratch.execute(sql)
        affected = scratch.total_changes
        scratch.rollback()
        return {"kind": "write", "affected_rows": affected}
    finally:
        scratch.close()
        source.close()


def execute(sql: str) -> dict:
    """Run a single statement safely and describe the result.

    Returns a dict with "kind": "read" (rows), "write" (affected_rows, nothing
    saved) or "not_run" (statement type we don't execute), or "error".
    """
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        return {"kind": "error", "error": "No query to run."}
    keyword = _first_keyword(sql)
    try:
        if keyword in WRITE_KEYWORDS:
            return _dry_run_write(sql)
        if keyword in READ_KEYWORDS:
            try:
                return _run_read(sql)
            except sqlite3.OperationalError as exc:
                # e.g. WITH ... DELETE: blocked by the read-only connection.
                if "readonly" in str(exc) or "read-only" in str(exc):
                    return _dry_run_write(sql)
                raise
        return {
            "kind": "not_run",
            "message": f"{keyword or 'This'} statements are shown but not executed.",
        }
    except sqlite3.Error as exc:
        message = str(exc)
        if message == "interrupted":
            message = f"The query took longer than {TIMEOUT_SECONDS} seconds and was stopped."
        return {"kind": "error", "error": message}
