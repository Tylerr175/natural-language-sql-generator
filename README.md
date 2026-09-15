# Natural Language SQL Tool

Ask a question in plain English, get back a real SQL query and the results — no SQL knowledge required.

I built this because I kept wanting to poke around a music dataset (Spotify-style track data: tempo, danceability, energy, all that) without writing joins by hand every time. So instead, you just type something like "what are the most danceable pop songs?" and Claude turns it into a query, runs it against the database, and hands back a table.

## How it works

1. Upload a SQLite `.db` file or a plain `.csv` (CSV gets auto-converted into a single-table SQLite database, with column types guessed from the data).
2. The app reads the schema — tables, columns, a sample row from each — and hands that to Claude along with your question.
3. Claude writes a `SELECT` query (only `SELECT` — nothing destructive gets through).
4. The query runs against your uploaded database and the results come back as JSON.

It also generates a few example questions tailored to whatever dataset you upload, so you're not staring at a blank box wondering what to ask.

## Running it locally

```bash
pip install -r requirements.txt
```

Create a `.env` file with your Anthropic API key:

```
ANTHROPIC_API_KEY=your-key-here
```

Then start the server:

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000` and upload a database.

## A few notes on the design

- **Sessions are per-visitor.** Each browser gets a cookie-based session ID, so if two people upload different databases at the same time, they don't step on each other.
- **Rate limited.** 30 questions per hour per session, so a stray bot (or an overly curious visitor) can't run up the Claude API bill.
- **Only `SELECT` queries get executed.** Even if something else slipped through, the app rejects it before it touches the database.
- **The sample database** (`music.db`) is a Spotify-style track dataset with artists, albums, genres, and per-track audio features (danceability, valence, tempo, etc.) — good for testing since it's got enough variety to ask interesting questions.

## Project layout

```
main.py           FastAPI backend — upload, schema reading, query endpoint
system_prompt.py  Builds the prompt that tells Claude how to write SQL for this schema
index.html        Frontend — upload form, question box, results table
music.db          Sample dataset
reference.md      Plain-English glossary of the concepts/code used here
```

## Deploying

Currently set up to run on Render's free tier. Free tier services spin down after inactivity, so if the site feels slow to respond on first load, that's just it waking back up.
