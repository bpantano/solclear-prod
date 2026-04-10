# Tools

Python scripts for deterministic execution. Each script does one thing reliably.

## Conventions

- Each script reads config/inputs from CLI args or environment variables
- Credentials come from `.env` (use `python-dotenv`)
- Output goes to stdout or a specified file/cloud destination
- Scripts are idempotent where possible

## Adding a New Tool

1. Create `tools/your_tool_name.py`
2. Add a docstring describing inputs, outputs, and any rate limits or gotchas
3. Reference it in the relevant workflow(s)
