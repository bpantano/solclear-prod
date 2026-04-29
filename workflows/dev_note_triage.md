# Dev Note Triage

## Purpose
Surface all unresolved bug flags before any new code is written. Run this at the start of a session or whenever Brandon asks for it.

## When to run
- Whenever Brandon says "run dev note triage", "check dev notes", or similar
- Before starting any new feature or fix sprint
- Never write new code in the same session until the triage has been discussed and prioritised

## Steps

### 1. Fetch open dev notes from the DB

Run the following query via `tools/db.py`:

```python
from tools.db import fetch_all
notes = fetch_all("""
    SELECT
        n.id,
        n.body,
        n.dev_status,
        n.created_at,
        req.code  AS requirement_code,
        req.title AS requirement_title,
        r.id      AS report_id,
        p.name    AS project_name,
        u.first_name || ' ' || u.last_name AS filed_by
    FROM notes n
    LEFT JOIN requirement_results rr ON rr.id = n.requirement_result_id
    LEFT JOIN requirements req        ON req.id = rr.requirement_id
    LEFT JOIN reports r               ON r.id = n.report_id
    LEFT JOIN projects p              ON p.id = r.project_id
    LEFT JOIN users u                 ON u.id = n.author_user_id
    WHERE n.visibility = 'dev'
      AND n.parent_note_id IS NULL
      AND n.dev_status IN ('open', 'acknowledged')
    ORDER BY n.created_at ASC
""")
```

### 2. For each note, output a triage card

Format each result as:

```
──────────────────────────────────────────
Note #<id> · Status: <dev_status> · Filed: <created_at date>
Filed by: <filed_by> on report <report_id> (<project_name>)
Requirement: <requirement_code> — <requirement_title>  (or "General" if no requirement)

BUG REPORT:
<body>

SUGGESTED FIX:
<1-3 sentence diagnosis and recommended code change>
──────────────────────────────────────────
```

### 3. Summarise at the end

After all cards, output:
- Total open notes
- Total acknowledged notes
- Which ones look highest priority (data loss / incorrect pass/fail verdict > UX > cosmetic)

### 4. Wait — do not write code

Present the triage output and ask Brandon which notes to address and in what order. Only begin writing code after he confirms the priority list.

## Edge cases
- If no open or acknowledged notes exist, say so and confirm it's safe to proceed with new work
- If the DB is unreachable, say so and skip the triage rather than silently continuing
- Replies (parent_note_id IS NOT NULL) are excluded — they are discussion threads, not separate bugs
