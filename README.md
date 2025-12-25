# Nephro Brain MVP

Minimal web app that ingests PubMed nephrology papers, adds heuristic summaries and PICO framing, and serves a mobile-first UI.

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ingest.py --days 3 --max-per-journal 5
python app.py
```

Open `http://127.0.0.1:5000`.

## What This MVP Does
- Pulls recent articles from PubMed using journal queries.
- Auto-tags with basic keyword rules.
- Generates heuristic summary, PICO, and practice impact signals.
- Allows saving favorites locally in SQLite.

## Notes
- This MVP uses rule-based heuristics in `ai.py` for summaries and PICO.
- Replace `ai.py` with an LLM pipeline for production accuracy.
- Data is stored in `db.sqlite3` (ignored by git).
