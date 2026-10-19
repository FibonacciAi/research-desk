<p align="center"><img src="assets/icon-512.png" width="128" alt="Research Desk logo"></p>

# Research Desk

**Sources in, approved findings out, as a clean SQL table.**

Give your agent a research goal and the sources you trust. It drafts findings, each with the source URL and a supporting quote. You approve or discard every one. Approved findings export as SQL (`CREATE TABLE` plus `INSERT`) or CSV, ready for Postgres, SQLite, Snowflake, BigQuery or a spreadsheet.

> Context.dev fetches the web; Research Desk turns sources into findings you approve or discard, then exports a clean SQL table.

Free and open source (MIT). No accounts, no API keys, no charges, no telemetry. Python 3.10+ standard library only.

## How it works

1. **Goal.** One sentence plus 1 to 5 URLs you trust.
2. **Draft findings.** Your agent reads the sources with its normal web tools and adds each finding as a draft: a short claim, the exact source URL, and a verbatim quote.
3. **Review.** You see the drafts as cards and say "approve 1, 3, 4; discard the rest". Nothing is approved without your explicit decision.
4. **Export.** Only approved findings go into the export. Pending and discarded drafts never do.

Everything lives in one local SQLite file. Research Desk itself makes no network calls and never writes to your warehouse; the export is a file or text you run wherever you want.

## Install

**Grok Bot / Cursor plugin:** add this repository (`https://github.com/FibonacciAi/research-desk`) as a plugin, or install Research Desk from the marketplace. You get two skills (`research-desk`, `review-and-export`) and a local stdio MCP server (`python3 ${CURSOR_PLUGIN_ROOT}/server/mcp_server.py`).

**Terminal only:**

```bash
git clone https://github.com/FibonacciAi/research-desk
cd research-desk
python3 bin/research-desk status
```

## Try it in one minute (fictional demo)

```bash
python3 bin/research-desk demo                  # Harborline Freight goal with 5 draft findings
python3 bin/research-desk list                  # see the drafts
python3 bin/research-desk approve 1 3 4
python3 bin/research-desk discard 2 5 --note "self-reported or unconfirmed"
python3 bin/research-desk export --out harborline.sql
```

Harborline Freight is invented and its URLs use the reserved `.example` domain. See [`examples/harborline/expected-export.sql`](examples/harborline/expected-export.sql) for the output shape.

In chat, just ask: *"Research Desk: load the demo, show me the drafts."* Then *"Approve 1, 3 and 4, discard 2 and 5, and export SQL."*

## MCP tools

| Tool | What it does |
|---|---|
| `research_desk_status` | Version, database path, counts |
| `start_goal` | Start a goal; returns its id |
| `list_goals` | Goals with pending / approved / discarded counts |
| `add_finding` | Add a draft: `goal_id`, `claim`, `source_url`, optional `quote` |
| `list_pending` | Drafts awaiting a decision (or `status`: approved, discarded, all) |
| `approve` / `discard` | Decide on finding ids (only on the user's explicit decision) |
| `export_sql` | Approved findings as SQL or CSV; optional `table`, `dialect`, `goal_id`, `out_path` |
| `load_demo` | Load the fictional Harborline goal |

The CLI (`bin/research-desk`) has the same actions; every command prints one JSON object.

## Export format

```sql
CREATE TABLE IF NOT EXISTS research_findings (
  id INTEGER NOT NULL, goal_id INTEGER, goal TEXT, claim TEXT NOT NULL,
  source_url TEXT NOT NULL, quote TEXT, note TEXT, approved_at TEXT
);
INSERT INTO research_findings (...) VALUES (...);
```

`--dialect` selects column types (`bigquery` uses `INT64`/`STRING`; the others use `INTEGER`/`TEXT`) and string escaping. `postgres` and `sqlite` double single quotes and leave backslashes as themselves, which matches SQLite and Postgres with `standard_conforming_strings` on (the server default). `snowflake` and `bigquery` also escape backslashes, because those engines treat `\` as an escape. `bigquery` writes a quote as `\'` and a real newline as `\n`. `--table` must be a plain identifier.

## Data and privacy

- Database: `$RESEARCH_DESK_HOME/desk.db`, else `$XDG_DATA_HOME/research-desk/desk.db`, else `~/.local/share/research-desk/desk.db`.
- Each install starts empty. Delete the file to start over.
- Source URLs must be `http(s)`. Web pages your agent reads are treated as untrusted data.

## Tests

```bash
python3 -m unittest discover -s tests -t .
bash scripts/e2e.sh
```

## License

MIT © 2026 sevenfourone studio · [sevenfourone.studio](https://sevenfourone.studio) · heydimitri@mail.grokbot.com
