---
name: review-and-export
description: Research Desk review and export. Use when the user wants to approve or discard draft research findings, see what is pending, or export approved findings as SQL (CREATE TABLE plus INSERT) or CSV for a warehouse or spreadsheet.
---

# Research Desk: approve or discard, then export

## Review
1. `list_pending` (CLI: `list`, optionally `--goal <id>`). Show each draft as a card: id, claim, source domain, quote.
2. Ask the user to decide. Accept plain answers like "approve 1, 3, 4; discard the rest".
3. Call `approve` / `discard` with exactly the ids they named (CLI: `approve 1 3 4`, `discard 2 5 --note "why"`). **Only on an explicit decision in this conversation.** If unsure, ask; never approve by default.
4. A decision is final for that finding. If they change their mind, add a corrected new finding instead.

## Export
- `export_sql` (CLI: `export`) returns approved findings only, as `CREATE TABLE IF NOT EXISTS research_findings (...)` plus one `INSERT` per row. Pending and discarded drafts are never included.
- Options: `goal_id`; `format` `sql` or `csv`; `table` (a plain identifier); `dialect` `postgres` (default), `sqlite`, `snowflake` or `bigquery` (column types, and string escapes for `snowflake` and `bigquery`); `out_path` to write a local file.
- Columns: `id, goal_id, goal, claim, source_url, quote, note, approved_at`.
- The export is a copy. Research Desk never connects to or writes into a warehouse; the user runs the SQL wherever they like (for example `psql -f research_findings.sql` or `sqlite3 desk.db < research_findings.sql`).

## Report
Finish with: goal, counts (approved / discarded / still pending), the export path or the SQL in a code block, and any conflicts the user may want to chase next.
