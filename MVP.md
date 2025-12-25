# Nephro Brain MVP v0.1

## Goal
Reduce daily literature triage to under 3 minutes by delivering a small, high-signal list with clinical framing.

## Target Users
- Nephrology attendings
- Nephrology fellows
- Internal medicine physicians who track nephrology literature

## Core MVP Scope
- Daily literature feed from a minimal source set
- Auto-tagging into nephrology-relevant topics
- AI summary with key takeaway, study type, primary outcome, and direction
- PICO breakdown (P, I, C, O)
- Practice impact rating with a short reason and disclaimer
- Favorites list for later review

## User Flow
1. Open app
2. See "Today" list (5-10 items)
3. Filter by tag
4. Open an article to see summary, PICO, impact
5. Save or ignore

## Data Sources (MVP)
- PubMed E-utilities (primary source)
- Journal RSS (NEJM, JAMA, Kidney International)

## Tags (MVP Set)
- CKD
- AKI
- HD
- PD
- Transplant
- Electrolyte disorders
- GN / IgA / Lupus
- Drug / RCT / Guideline

## Article Data Model (MVP)
- id
- title
- abstract
- journal
- publish_date
- url
- tags[]
- key_takeaway
- study_type
- primary_outcome
- outcome_direction (up / down / no difference)
- pico { P, I, C, O }
- impact { level: yes / possibly / no, reason }
- created_at
- updated_at

## MVP Acceptance Criteria
- Daily ingest runs end-to-end on schedule
- 5-10 new items appear per day
- Tag filter works on the list view
- Detail view shows summary, PICO, and impact
- Favorites persist per device
- "Not a clinical recommendation" disclaimer is shown on detail view

## Out of Scope (v0.1)
- Full-text parsing
- Personalized recommendations
- User accounts or multi-device sync
- Notifications or email digests
- Custom tag definitions or complex search
- Multi-language UI

## Implementation Sketch
- Backend: Python ingestion job + SQLite
- LLM: summary, PICO, impact classification
- Frontend: mobile-first web app
- API:
  - GET /articles?date=YYYY-MM-DD&tag=...
  - GET /articles/:id
  - POST /favorites

## Next Iteration
- Add CJASN, AJKD, CKJ sources
- Improve tagging with MeSH terms + classifier
- Saved searches and journal club exports
