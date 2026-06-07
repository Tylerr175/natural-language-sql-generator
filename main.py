import os
import csv
import io
import time
import uuid
import sqlite3
import tempfile
import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from system_prompt import get_system_prompt

load_dotenv()

app = FastAPI()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Caps how many questions a single session can ask Claude in a given
# stretch of time. Without this, one visitor (or a bot) could run up
# the API bill or hammer the server with no limit at all.
RATE_LIMIT_MAX = 30        # max questions allowed...
RATE_LIMIT_WINDOW = 3600   # ...within this many seconds (1 hour)

# One entry per visitor, keyed by a session ID stored in a cookie.
# This keeps each person's uploaded database completely separate —
# without it, every visitor would share the same database.
sessions: dict[str, dict] = {}


def get_session_id(request: Request, response: Response) -> str:
    """Reads the visitor's session ID from their cookie. If they don't
    have one yet (first visit), generates a new one, sets it as a cookie
    so the browser sends it back on future requests, and creates an
    empty session entry for it."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        session_id = uuid.uuid4().hex
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        sessions[session_id] = {
            "path": None,
            "schema": None,
            "filename": None,
            "suggestions": [],
            "query_log": [],
            "history": [],
        }
    return session_id


def check_rate_limit(session: dict) -> bool:
    """Returns True if this session is allowed to run another query right
    now, and records the attempt. Keeps a rolling timestamp log per session
    — anything older than the window is dropped — so a single visitor can't
    burn through the Claude API budget."""
    now = time.time()
    recent = [t for t in session["query_log"] if now - t < RATE_LIMIT_WINDOW]
    if len(recent) >= RATE_LIMIT_MAX:
        session["query_log"] = recent
        return False
    recent.append(now)
    session["query_log"] = recent
    return True


def sanitize_table_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = "".join(c if c.isalnum() else "_" for c in name)
    if not name or name[0].isdigit():
        name = "t_" + name
    return name


def infer_column_type(values: list[str]) -> str:
    """Looks at every non-empty value in a column and picks the most
    specific SQLite type that fits all of them."""
    non_empty = [v for v in values if v != ""]
    if not non_empty:
        return "TEXT"

    def is_int(v):
        try:
            int(v)
            return True
        except ValueError:
            return False

    def is_float(v):
        try:
            float(v)
            return True
        except ValueError:
            return False

    if all(is_int(v) for v in non_empty):
        return "INTEGER"
    if all(is_float(v) for v in non_empty):
        return "REAL"
    return "TEXT"


def csv_to_sqlite(csv_text: str, db_path: str, table_name: str):
    """Reads CSV text, infers a type for each column, and builds a
    single-table SQLite database file from it."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if len(rows) < 2:
        raise ValueError("CSV file has no data rows")

    headers = rows[0]
    data_rows = rows[1:]

    # Pad or trim every row so it matches the header length —
    # handles CSVs where some rows have missing trailing values
    normalized_rows = []
    for row in data_rows:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        normalized_rows.append(row[:len(headers)])

    column_types = [
        infer_column_type([row[i] for row in normalized_rows])
        for i in range(len(headers))
    ]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    column_defs = ", ".join(f'"{name}" {ctype}' for name, ctype in zip(headers, column_types))
    cursor.execute(f'CREATE TABLE "{table_name}" ({column_defs})')

    placeholders = ", ".join("?" for _ in headers)
    cursor.executemany(f'INSERT INTO "{table_name}" VALUES ({placeholders})', normalized_rows)

    conn.commit()
    conn.close()


def read_schema(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    schema = {}
    for table in tables:
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = [{"name": row[1], "type": row[2] or "TEXT"} for row in cursor.fetchall()]

        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        row_count = cursor.fetchone()[0]

        # Grab one real row so Claude can see the actual shape of the data,
        # not just the column name and type
        cursor.execute(f'SELECT * FROM "{table}" LIMIT 1')
        sample_row = cursor.fetchone()
        if sample_row:
            for i, col in enumerate(columns):
                col["sample"] = sample_row[i]

        schema[table] = {"columns": columns, "row_count": row_count}
    conn.close()
    return schema


def schema_to_text(schema: dict) -> str:
    lines = ["The database has the following tables:\n"]
    for table_name, info in schema.items():
        lines.append(f"TABLE: {table_name} ({info['row_count']} rows)")
        for col in info["columns"]:
            sample = col.get("sample")
            sample_text = f" — example value: {sample!r}" if sample is not None else ""
            lines.append(f"- {col['name']} ({col['type']}){sample_text}")
        lines.append("")
    lines.append(
        "IMPORTANT: Some text columns may store dates, numbers, or codes in non-standard "
        "formats (e.g. 'Feb 2 2020' instead of '2020-02-02'). Look at the example values "
        "above before writing ORDER BY, comparisons, or filters on them — sorting a "
        "non-standard date as plain text gives the wrong order. Convert it to a sortable "
        "form first if needed."
    )
    return "\n".join(lines)


def generate_suggestions(schema_text: str) -> list[str]:
    """Asks Claude for a few example questions tailored to this exact
    dataset, so a person facing an unfamiliar schema has something to
    click instead of staring at a blank input box."""
    prompt = (
        f"Here is a database schema:\n\n{schema_text}\n\n"
        "Write exactly 4 short, natural-sounding questions a curious person "
        "might ask about this data. Each under 12 words. Return them as a "
        "plain list, one per line, with no numbering, bullets, or extra text."
    )
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = message.content[0].text.strip().splitlines()
        cleaned = [line.strip(" -•0123456789.").strip() for line in lines]
        return [line for line in cleaned if line][:4]
    except Exception:
        return []


def run_query(sql: str, db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/")
def root():
    return FileResponse("index.html")


@app.post("/upload")
async def upload_db(request: Request, response: Response, file: UploadFile = File(...)):
    session_id = get_session_id(request, response)
    session = sessions[session_id]

    filename_lower = file.filename.lower()
    is_csv = filename_lower.endswith(".csv")
    is_sqlite = filename_lower.endswith((".db", ".sqlite", ".sqlite3"))

    if not (is_csv or is_sqlite):
        return {"error": "File must be a SQLite database (.db, .sqlite, .sqlite3) or a CSV file (.csv)"}

    contents = await file.read()

    # Each session gets its own uniquely-named file, so two visitors
    # uploading at the same time never collide or overwrite each other
    temp_path = os.path.join(tempfile.gettempdir(), f"querydb_{session_id}.sqlite")

    # Remove this session's previous database (if any) so CSV
    # conversion always starts from a clean file
    if os.path.exists(temp_path):
        os.remove(temp_path)

    if is_csv:
        try:
            csv_text = contents.decode("utf-8-sig")
            table_name = sanitize_table_name(file.filename)
            csv_to_sqlite(csv_text, temp_path, table_name)
        except Exception as e:
            return {"error": f"Could not read CSV file: {str(e)}"}
    else:
        with open(temp_path, "wb") as f:
            f.write(contents)

    try:
        schema = read_schema(temp_path)
    except Exception as e:
        return {"error": f"Could not read database: {str(e)}"}

    suggestions = generate_suggestions(schema_to_text(schema))

    session["path"] = temp_path
    session["schema"] = schema
    session["filename"] = file.filename
    session["suggestions"] = suggestions
    session["history"] = []

    return {"filename": file.filename, "schema": schema, "suggestions": suggestions}


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
def query(request: Request, response: Response, body: QueryRequest):
    session_id = get_session_id(request, response)
    session = sessions[session_id]

    if not session["path"]:
        return {
            "question": body.question,
            "sql": None,
            "results": [],
            "error": "No database loaded. Upload a .db file first.",
            "history": session["history"],
        }

    if not check_rate_limit(session):
        return {
            "question": body.question,
            "sql": None,
            "results": [],
            "error": (
                f"You've reached the limit of {RATE_LIMIT_MAX} questions per hour. "
                "Please wait a bit and try again."
            ),
            "history": session["history"],
        }

    # Record this question in the session's history — newest first, no
    # duplicates, capped at 10 — so the frontend can offer a "rerun" list.
    history = [q for q in session["history"] if q != body.question]
    history.insert(0, body.question)
    session["history"] = history[:10]

    schema_text = schema_to_text(session["schema"])
    system = get_system_prompt(schema_text)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": body.question}],
    )

    sql = message.content[0].text.strip()

    if not sql.upper().startswith("SELECT"):
        return {
            "question": body.question,
            "sql": sql,
            "results": [],
            "error": "Only SELECT queries are allowed.",
            "history": session["history"],
        }

    try:
        results = run_query(sql, session["path"])
        return {"question": body.question, "sql": sql, "results": results, "error": None, "history": session["history"]}
    except Exception as e:
        return {"question": body.question, "sql": sql, "results": [], "error": str(e), "history": session["history"]}
