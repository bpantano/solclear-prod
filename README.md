# Solclear

Automated compliance checking for residential solar installations. Solclear connects to CompanyCam, pulls installation photos, and uses AI vision to verify they meet lender documentation requirements — before the crew leaves the job site.

## What It Does

1. **Crew selects a project** from CompanyCam on their phone
2. **Picks the checklist** applied to that project
3. **Selects the manufacturer** (SolarEdge, Tesla, Enphase)
4. **AI checks each photo** against Palmetto M1 requirements in real time
5. **Results stream live** — PASS/FAIL per requirement with explanations
6. **Persistent reports** — bookmarkable, shareable, re-runnable

## Tech Stack

- **Backend:** Python (stdlib `http.server` + SSE)
- **Database:** PostgreSQL on Railway
- **AI:** Claude Haiku (vision) via Anthropic API
- **Photos:** CompanyCam API
- **Hosting:** Railway
- **Frontend:** Embedded HTML/CSS/JS (no build step)

## Local Development

```bash
# Clone
git clone https://github.com/bpantano/solclear-dev.git
cd solclear-dev

# Install dependencies
pip install -r requirements.txt

# Set up .env
cp .env.example .env
# Fill in COMPANYCAM_API_KEY, ANTHROPIC_API_KEY, DATABASE_URL

# Run locally
python tools/live_server.py
# Open http://localhost:8080
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `COMPANYCAM_API_KEY` | Yes | CompanyCam API bearer token |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude Vision |
| `DATABASE_URL` | Yes | PostgreSQL connection string |

## Project Structure

```
tools/                  # Python scripts (WAT framework "Tools")
  live_server.py        # Main web server with SSE streaming
  compliance_check.py   # AI vision compliance checker
  db.py                 # PostgreSQL helper module
  generate_report_html.py  # Static HTML report generator
  companycam_*.py       # CompanyCam API tools
  monitor_requirements.py  # Palmetto requirements change detector
workflows/              # Markdown SOPs
knowledgebase/          # Palmetto M1 requirements reference
branding/               # SVG logos and brand assets
schema.sql              # PostgreSQL schema
```

## Repos

- **solclear-dev** — active development
- **solclear-prod** — stable, deployed to Railway
