# Code Reference Guide
A plain-English glossary of every concept used in this project. Updated as we build.

---

## General Concepts

**Server**
A program that runs continuously, listens for incoming requests, and sends back responses. In this project, uvicorn is the server.

**Endpoint**
A specific URL path your server responds to. Example: `/test-db` is an endpoint. Each endpoint does one job.

**JSON**
JavaScript Object Notation. A text format for sending data between a server and a browser. Looks like a Python dictionary: `{"key": "value"}`. FastAPI converts Python dicts to JSON automatically.

**Decorator**
A line starting with `@` that sits above a function and adds behavior to it. `@app.get("/")` tells FastAPI to run the function below it whenever someone visits that URL path.

---

## Packages

**fastapi**
The web framework. Handles incoming requests and outgoing responses. You define endpoints and FastAPI does the routing.

**uvicorn**
The server engine that runs FastAPI. You start it with `uvicorn main:app --reload`. The `--reload` flag makes it restart automatically every time you save a file.

**anthropic**
Anthropic's official Python package. Handles all communication with Claude's API so you don't write raw HTTP requests yourself.

**sqlite3**
Built into Python — no install needed. Lets Python read and write SQLite database files.

---

## main.py — Line by Line

### Imports
**`import sqlite3`**
Loads the sqlite3 module so Python can talk to .db files.

**`from fastapi import FastAPI`**
Pulls the FastAPI class out of the fastapi package so you can use it.

---

### Setup
**`app = FastAPI()`**
Creates your application instance. Everything else (endpoints, settings) attaches to this object.

**`DB_PATH = "music.db"`**
Stores the database filename in one variable. If the file ever moves or gets renamed, you only update this one line.

---

### run_query() function
**`def run_query(sql: str):`**
Defines a reusable function. The `: str` is a type hint — it tells Python (and you) that `sql` should be a string.

**`conn = sqlite3.connect(DB_PATH)`**
Opens a connection to the database file. Like opening a door — you must close it when done.

**`conn.row_factory = sqlite3.Row`**
Changes how SQLite returns data. Without this, rows come back as plain tuples like `(1, "Die With A Smile")`. With this, they behave like dictionaries: `{"track_id": 1, "title": "Die With A Smile"}`.

**`cursor = conn.cursor()`**
Creates a cursor — the object you use to actually send SQL commands. The connection is the door, the cursor is your hand reaching through it.

**`cursor.execute(sql)`**
Sends the SQL query to the database and runs it.

**`rows = cursor.fetchall()`**
Retrieves every result row from the query.

**`conn.close()`**
Closes the database connection. Always close what you open.

**`return [dict(row) for row in rows]`**
Converts each Row object into a plain Python dictionary, then returns a list of all of them. This is a list comprehension — a compact way of looping and transforming in one line.

---

### Endpoints
**`@app.get("/")`**
Registers the function below it as a GET endpoint at the root path. A GET request means "give me data" (as opposed to POST, which means "here is data").

**`@app.get("/test-db")`**
Same idea — registers a GET endpoint at `/test-db`. Used to verify the database connection works before adding Claude.

---

## system_prompt.py — Concepts

**System Prompt**
A set of instructions sent to Claude before the user's question. It establishes Claude's role, tells it what data exists, and shows it examples. The better the system prompt, the more accurate the SQL output.

**Few-Shot Prompting**
A technique where you give an AI model a few worked examples (question → answer pairs) before asking your real question. Claude pattern-matches against them. More examples = better accuracy.

**ROLE**
The section of the system prompt that defines Claude's job and rules. Stays the same regardless of the database.

**SCHEMA**
The section that describes every table and column in the database. This is how Claude knows what data is available to query.

**EXAMPLES**
The section with hand-written question-to-SQL pairs. These are the most important part for accuracy.

**`get_system_prompt()`**
A function that assembles ROLE + SCHEMA + EXAMPLES into one string. This string gets sent to Claude's API on every request.

---

## SQLite Concepts

**SQLite**
A database that lives in a single file on your computer (.db file). No server required. Perfect for projects like this.

**Table**
A grid of data with rows and columns — like a spreadsheet. This project has 4: artists, albums, genres, tracks.

**Primary Key**
A column that uniquely identifies each row. Example: `artist_id` in the artists table. No two rows can have the same primary key.

**Foreign Key**
A column in one table that points to a primary key in another table. Example: `tracks.artist_id` points to `artists.artist_id`. This is how tables are linked.

---

## SQL Keywords

The building blocks of every SQL query. A query is just a sentence built from these words in a specific order.

---

### Retrieving Data

**`SELECT`**
Chooses which columns to include in your results. Think of it as "give me these specific pieces of information."
```sql
SELECT title, popularity   -- only return these two columns
```
Use `SELECT *` to return every column (the `*` means "all").

**`FROM`**
Tells SQL which table to pull data from. Every query starts with SELECT and FROM.
```sql
SELECT title FROM tracks   -- get the title column from the tracks table
```

**`WHERE`**
Filters rows. Only rows that match the condition are returned. Think of it as "but only if..."
```sql
SELECT title FROM tracks WHERE popularity > 90   -- only songs with popularity above 90
```

**`LIMIT`**
Caps the number of rows returned. Prevents getting thousands of results when you only want the top 10.
```sql
SELECT title FROM tracks LIMIT 5   -- return only the first 5 results
```

**`DISTINCT`**
Removes duplicate values from results. Only returns unique entries.
```sql
SELECT DISTINCT genre FROM genres   -- each genre name appears once, not repeated
```

---

### Sorting

**`ORDER BY`**
Sorts the results by a column. Default is ascending (lowest to highest).
```sql
SELECT title, popularity FROM tracks ORDER BY popularity   -- sorted low to high
```

**`DESC`**
Short for "descending." Used with ORDER BY to sort highest to lowest.
```sql
ORDER BY popularity DESC   -- most popular first
```

**`ASC`**
Short for "ascending." Lowest to highest. This is the default, so you rarely need to write it explicitly.
```sql
ORDER BY popularity ASC   -- least popular first
```

---

### Joining Tables

**`JOIN`** (also written `INNER JOIN`)
Combines rows from two tables where a column matches. Used when your question needs data from more than one table. If you ask "what is the artist name for this track?" — the track is in `tracks`, the name is in `artists` — you need a JOIN.
```sql
FROM tracks t JOIN artists a ON t.artist_id = a.artist_id
```

**`ON`**
The condition that tells JOIN how to match the two tables. Almost always connects a foreign key to a primary key.
```sql
ON t.artist_id = a.artist_id   -- match where these two columns are equal
```

**`LEFT JOIN`**
Like a regular JOIN, but keeps all rows from the left table even if there's no match in the right table. Missing values show up as NULL. Not used often in this project but worth knowing.

---

### Aliases

**`AS`**
Renames a column or table in the results. Makes output cleaner and is required when you use aggregate functions.
```sql
SELECT a.name AS artist   -- the column shows up labeled "artist" instead of "name"
```
You can also alias table names for shorthand:
```sql
FROM tracks t   -- "t" is now a shortcut for "tracks" throughout the query
```

---

### Grouping & Aggregates

Aggregate functions collapse many rows into one summary value.

**`GROUP BY`**
Groups rows that share a value, then lets you run aggregate functions on each group. Example: group all tracks by genre, then count how many are in each.
```sql
GROUP BY g.genre   -- one result row per unique genre
```

**`COUNT()`**
Counts how many rows are in a group.
```sql
SELECT a.name, COUNT(*) AS song_count   -- how many tracks each artist has
```

**`AVG()`**
Calculates the average value of a column across a group.
```sql
AVG(t.energy)   -- average energy score for the group
```

**`SUM()`**
Adds up all values in a column across a group.
```sql
SUM(t.duration_ms)   -- total duration of all songs in the group
```

**`MAX()`**
Returns the highest value in a column.
```sql
MAX(t.popularity)   -- the highest popularity score
```

**`MIN()`**
Returns the lowest value in a column.
```sql
MIN(t.tempo)   -- the slowest tempo
```

**`ROUND()`**
Rounds a decimal number to a specified number of places. Used to keep results clean.
```sql
ROUND(AVG(t.energy), 3)   -- round to 3 decimal places, e.g. 0.714
```

---

### Filtering Text

**`LIKE`**
Pattern matching for text. Used with `%` as a wildcard (meaning "anything can go here").
```sql
WHERE LOWER(a.name) LIKE '%bruno%'   -- matches "Bruno Mars", "Lady Gaga, Bruno Mars", etc.
```
`%bruno%` means: anything, then "bruno", then anything.

**`LOWER()`**
Converts text to lowercase before comparing. Prevents misses when data has inconsistent capitalization.
```sql
WHERE LOWER(g.genre) = 'pop'   -- matches 'pop', 'Pop', 'POP'
```

**`UPPER()`**
Same as LOWER() but converts to uppercase instead. Less commonly used.

---

### Combining Conditions

**`AND`**
Both conditions must be true for the row to be included.
```sql
WHERE g.genre = 'rock' AND t.valence < 0.3   -- must be rock AND sad
```

**`OR`**
Either condition can be true.
```sql
WHERE g.genre = 'pop' OR g.genre = 'indie'   -- pop songs or indie songs
```

**`NOT`**
Reverses a condition. Rarely used but good to know.
```sql
WHERE NOT g.genre = 'classical'   -- everything except classical
```

---

### Handling Missing Data

**`NULL`**
Represents a missing or unknown value. Not the same as zero or an empty string — it means the value simply isn't there. One track in this database has NULL audio features.

**`IS NULL`**
Checks if a value is missing.
```sql
WHERE t.danceability IS NULL   -- find rows with no danceability value
```

**`IS NOT NULL`**
Checks if a value exists (is not missing).
```sql
WHERE t.danceability IS NOT NULL   -- only rows that have a danceability value
```

---

### A Full Query — Annotated

```sql
SELECT t.title, a.name AS artist, t.popularity   -- which columns to return
FROM tracks t                                     -- main table, aliased as "t"
JOIN artists a ON t.artist_id = a.artist_id       -- bring in artist names
WHERE t.popularity > 80                           -- filter: only popular songs
ORDER BY t.popularity DESC                        -- sort: most popular first
LIMIT 10                                          -- only return top 10
```
Reading order in plain English: "Give me the title, artist name, and popularity score, from the tracks table linked to the artists table, but only for tracks with popularity above 80, sorted most popular first, and stop after 10 results."

---

## main.py — Phase 3 Additions (Claude Integration)

**`from fastapi.responses import FileResponse`**
Imports a FastAPI tool that sends an actual file (like an HTML page) back to the browser. Used to serve `index.html` from the root `/` endpoint.

**`from pydantic import BaseModel`**
Pydantic is FastAPI's data validation library. Used to define the shape of incoming POST request bodies.

**`class QueryRequest(BaseModel): question: str`**
Defines what a valid request to `/query` must look like — it must have a `question` field that is a string. FastAPI automatically rejects any request that doesn't match this shape.

**`client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))`**
Creates the Claude API client. `os.environ.get()` reads the API key from the `.env` file (loaded by `load_dotenv()`). This client is created once and reused on every request.

**`client.messages.create(...)`**
Sends a request to Claude's API. Key parameters:
- `model` — which Claude model to use
- `max_tokens` — the maximum length of Claude's response (500 is plenty for SQL)
- `system` — the system prompt (ROLE + SCHEMA + DATASET_NOTES + EXAMPLES)
- `messages` — the conversation, starting with the user's question

**`message.content[0].text.strip()`**
Extracts Claude's response text. `.content[0]` gets the first content block, `.text` gets the string, `.strip()` removes any extra whitespace or newlines.

**`@app.post("/query")`**
A POST endpoint. POST is used when you're sending data to the server (the user's question), as opposed to GET which just retrieves data.

---

## main.py — Phase 5 Additions (Safety & Error Handling)

**`if not sql.upper().startswith("SELECT"):`**
A safety check that runs before any SQL touches the database. `.upper()` normalizes the case so `select`, `SELECT`, and `Select` all get caught. If Claude ever generates a DELETE, DROP, UPDATE, or any other non-SELECT statement, this blocks it immediately and returns an error — the database is never touched.

**`try:` / `except Exception as e:`**
A try/except block wraps the database call. If Claude generates invalid SQL (wrong column name, broken JOIN, etc.), the except block catches the crash, converts the error to a readable string with `str(e)`, and returns it as clean JSON. The app keeps running instead of crashing.

**`"error": None`**
Every `/query` response now always includes an `error` field. On success it's `None`. On failure it's a message string. The frontend always checks this same field — one consistent response shape regardless of outcome.

---

## index.html — Concepts

**HTML**
HyperText Markup Language. The structure of a web page. Tags like `<div>`, `<input>`, `<table>` define what elements exist on the page.

**CSS**
Cascading Style Sheets. Controls how HTML elements look — colors, sizes, spacing, layout. Lives inside `<style>` tags in the `<head>`.

**JavaScript**
The programming language that runs in the browser. Makes the page interactive — handles button clicks, sends requests, and updates what the user sees without reloading.

**`<head>`**
The section of an HTML file that contains metadata — not visible on the page. Holds the title (shown in browser tab) and CSS styles.

**`<body>`**
The section containing everything the user actually sees and interacts with.

**`display: flex`**
A CSS layout mode. When applied to a container, its children line up side by side in a row. Used to put the input and button on the same line.

**`flex: 1`**
Tells a flex child to stretch and fill all remaining space. Applied to the input box so it expands to fill the row, leaving just enough room for the button.

**`display: none`**
Hides an element completely. Applied to the SQL box by default — JavaScript removes this when a query runs.

**`async function`**
A JavaScript function that can pause and wait for slow operations without freezing the page. Required when making network requests.

**`await`**
Pauses execution inside an async function until the operation finishes. Without it, JavaScript would move on before the server responded.

**`fetch()`**
The browser's built-in tool for making HTTP requests to a server. Takes a URL and options (method, headers, body) and returns the server's response.

**`JSON.stringify()`**
Converts a JavaScript object into a JSON string so it can be sent in a request body. Example: `{ question: "hello" }` → `'{"question":"hello"}'`.

**`response.json()`**
Parses the JSON text the server sends back into a JavaScript object you can work with.

**`document.getElementById()`**
Finds an HTML element on the page by its `id` attribute. Used to read input values and update content.

**`innerHTML`**
A property that gets or sets the HTML content inside an element. Used to inject the results table into the page after a query runs.

**`button.disabled = true`**
Prevents the button from being clicked while a request is in progress. Prevents the user from sending duplicate requests.

**`??` (nullish coalescing operator)**
Returns the right side if the left side is `null` or `undefined`. Used as `row[col] ?? ""` — if a database value is NULL, display an empty string instead of the word "null".

**`addEventListener("keydown", ...)`**
Listens for a key being pressed. Used to let the user press Enter instead of clicking the button.

---

## Project Files

**`main.py`** — The FastAPI backend. Serves the HTML page, connects to the database, calls Claude, and returns results.

**`system_prompt.py`** — Builds the instruction set sent to Claude on every request. Contains ROLE, SCHEMA, DATASET_NOTES, and EXAMPLES.

**`index.html`** — The frontend web page. Text input, results table, SQL display, and all interactivity.

**`music.db`** — The SQLite database file. Contains 4 tables: artists, albums, genres, tracks.

**`.env`** — Stores the Anthropic API key. Never shared or committed to git.

**`.gitignore`** — Tells git to ignore `.env` so the API key is never accidentally uploaded.

**`requirements.txt`** — Lists every Python package the project needs, with exact version numbers. Used by hosting platforms to install dependencies before running the app.

**`reference.md`** — This file. A plain-English glossary of every concept used in the project.

---
*Updated through: Phase 5 (Safety, error handling, frontend polish)*
