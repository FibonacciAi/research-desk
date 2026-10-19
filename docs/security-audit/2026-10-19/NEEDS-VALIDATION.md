# Needs validation

Four leads. No severity. None of these is a confirmed vulnerability. Do not send them to a live warehouse, a shared host, or another person's database.

## Default research database is created without a private file mode

Fingerprint: `research_desk/store.py:default_home/desk.db-file-mode`

Claimed cause: `Desk.__init__` creates the default data directory with `Path.mkdir`'s default mode and opens `desk.db` with `sqlite3.connect` without `chmod`.

Trace:

1. `server/mcp_server.py:40` `call` — MCP `api.status()` passes no database path. The CLI does the same when `--db` is omitted.
2. `research_desk/api.py:12` `_with` — `Desk(db)` with `db` omitted.
3. `research_desk/store.py:71` `Desk.__init__` — `db_path is None` selects `default_home`.
4. `research_desk/store.py:54` `default_home` — `RESEARCH_DESK_HOME`, else `XDG_DATA_HOME` or `~/.local/share`, then `research-desk`.
5. `research_desk/store.py:73` `Desk.__init__` — `mkdir` with no mode.
6. `research_desk/store.py:76` `Desk.__init__` — `sqlite3.connect` creates `desk.db` with no `chmod`.

Evidence: source has no permission call on this path. The promoted artifact `agents/verifier-dbmode/artifacts/boundary-report.json` records `data_dir_mode` `0o755` and `desk_db_mode` `0o644` under umask `022`. The sandbox parent was a harness directory at `0755`.

Blockers:

- No second OS account opened `desk.db`.
- The real operator home mode was not measured, so traversability of the `0644` file is unknown.

Boundary: another local OS user, and the default `desk.db` of the launching user.

Local plan: on a disposable two-uid fixture, with umask `022`, create one parent at mode `0700` and another at mode `0755`. Set `RESEARCH_DESK_HOME` to a new subdirectory of each, construct `Desk()` with no db path, and have the second uid attempt only to open each resulting `desk.db`. Record `EACCES` or a successful open. Use empty databases and leave the operator home untouched.

Owner plan: run `stat -c %a` on `$HOME`, `$HOME/.local`, `$HOME/.local/share`, and on `$XDG_DATA_HOME` and `$RESEARCH_DESK_HOME` when set. Report whether a different local account can traverse that chain to the default `desk.db`. Leave modes unchanged and do not print database contents.

## Approved CSV export emits a claim that starts with equals and has no formula prefix

Fingerprint: `research_desk/store.py:csv.DictWriter:no-formula-prefix`

Claimed cause: `Desk.export` for format `csv` uses `csv.DictWriter` with `EXPORT_COLUMNS` and a newline terminator, then writes the approved row dicts. No code prefixes a leading equals sign.

Trace:

1. `server/mcp_server.py:43` `call` — `add_finding` stores the agent-supplied claim and quote. The research skill tells the agent to copy a verbatim quote.
2. `research_desk/api.py:40` `add_finding` — no character screening.
3. `research_desk/store.py:113` `Desk.add_finding` — stripped claim and quote are inserted. `check_url` does not alter the claim.
4. `research_desk/store.py:152` `Desk.approved_rows` — export copies the row only when status is approved.
5. `research_desk/store.py:165` `Desk.export` — `csv.DictWriter` with default minimal quoting writes a claim that starts with `=` and adds no formula prefix.

Evidence: `agents/verifier-csv/artifacts/boundary-report.json` `csv_text` has an unquoted claim cell `=1+1`, quote text `ordinary quote`, https source URLs, and only the approved rows. README line 7 names a spreadsheet as a CSV consumer.

Blocker: spreadsheet evaluation of that cell was not run. This environment has no spreadsheet engine.

Boundary: an approved claim whose text came from page content, and a later spreadsheet that opens the CSV.

Local plan: repeat `Desk.export` with format `csv` for one approved finding whose claim is the five characters `=1+1` and whose quote is ordinary quote. Confirm the claim cell is unquoted and has no prefix, and that a still-pending row is absent. Do not open the text in a spreadsheet.

Owner plan: on the operator's own computer, open that exported CSV in the spreadsheet already used for Research Desk exports and record whether the claim cell whose text is `=1+1` is calculated or shown as literal text, including the application name. Keep the file local.

## BigQuery export reuses apostrophe-only SQL quoting

Fingerprint: `research_desk/store.py:sql_literal:one-encoder-vs-bigquery-string-rules`

Claimed cause: dialect `bigquery` is rendered by the same `sql_literal` as every other dialect. Strings are single-quoted, apostrophes are doubled, and a backslash or newline is copied. `DIALECTS` selects only `INT64` and `STRING` for that name. README, `SECURITY.md`, and the export skill describe the dialect switch as a column-type change and the values as SQL string literals.

Trace:

1. `server/mcp_server.py:43` `call` — `add_finding` accepts caller-supplied claim and quote.
2. `research_desk/api.py:39` `add_finding` — forwards them to `Desk.add_finding`.
3. `research_desk/store.py:111` `Desk.add_finding` — parameterized insert. `check_url` does not scrub quotes or backslashes.
4. `research_desk/store.py:139` `Desk._decide` — parameterized update to `approved`.
5. `research_desk/store.py:152` `Desk.approved_rows` — approved rows only.
6. `server/mcp_server.py:47` `call` — `export_sql` passes the selected dialect. The schema lists `bigquery`.
7. `research_desk/api.py:55` `export` — dialect is forwarded.
8. `research_desk/store.py:172` `Desk.export` — SQL text is `to_sql`.
9. `research_desk/store.py:195` `to_sql` — `bigquery` is a `DIALECTS` key and every column goes through `sql_literal`.
10. `research_desk/store.py:196` `to_sql` — those quoted values are placed in the INSERT text.

Evidence: `sql_literal` at `research_desk/store.py:180` is the only export quoter. The bigquery map at line 41 is `INT64` / `STRING`. `tests/test_desk.py:71` runs a sqlite export with `executescript`. `tests/test_desk.py:85` only asserts that the bigquery text contains `STRING`. The promoted artifact records the doubled-apostrophe spelling, the backslash-then-apostrophe spelling, and a raw newline inside quotes, plus a sqlite readback of ordinary claims. It contains no BigQuery parse.

Blockers:

- No file in this repository states a BigQuery string grammar.
- The syntax-error versus early-end distinction was not observed.
- Tests execute export text only for dialect `sqlite`.

Boundary: approved export text for dialect `bigquery`, and a BigQuery job that parses that text.

Local plan: in scratch, run a throwaway lexer on only the three spellings `sql_literal` already emits for one approved row: the doubled-apostrophe form, the backslash-then-apostrophe form recorded as `sql_literal_backslash_quote`, and a quoted value that still contains a raw newline. Point the lexer at a BigQuery string production that is already on local disk. For each spelling, record one outcome: one complete string token whose decoded characters equal the original value; a syntax error that rejects the statement; or an early end, where the opening quote closes before the encoder's final quote and leftover tokens remain inside that same INSERT.

Owner plan: create a throwaway empty dataset that holds no production tables. Export one approved row with dialect `bigquery` whose string values contain an apostrophe, a backslash followed by an apostrophe, and a newline. Submit that export's `CREATE TABLE` and its one `INSERT`. Record whether the job reports a syntax error before any row is written, writes a cell equal to the original characters, or ends the literal before the encoder's closing quote while still parsing that same statement. Keep the job on that empty dataset.

## Approve and discard commit pending ids with no stored user decision

Fingerprint: `research-desk.mcp.approve.prompt-only-binding`

Claimed cause: `Desk._decide` updates a pending finding from the caller-supplied id and optional note. The findings table stores status, note, and `decided_at`. The MCP input schema has no confirmation or utterance field.

Trace:

1. `server/mcp_server.py:44` `call` — `list_pending` returns stored finding rows to the host.
2. `research_desk/store.py:133` `Desk.list_findings` — each row includes claim, source URL, and quote.
3. `server/mcp_server.py:45` `call` — `approve` forwards `finding_ids` and an optional note. The next line does the same for `discard`.
4. `research_desk/store.py:139` `Desk._decide` — a still-pending row is updated and committed. `approved_rows` can later export it.

Evidence: the approve tool text (`server/mcp_server.py:30`), the initialize instructions (`server/mcp_server.py:60`), the key check (`server/mcp_server.py:71`), the findings columns (`research_desk/store.py:32`), the pending check (`research_desk/store.py:137`), the approved filter (`research_desk/store.py:153`), `skills/review-and-export/SKILL.md:11`, and README line 17. All of the decision language is documentation or tool description. `tools/call` does not read it.

Blockers:

- The host model is outside this repository. Source cannot show whether stored quote, claim, or source URL text causes that model to call `approve` or `discard` for an id the operator did not name.
- A direct `approve` from this process only updates the launching user's database. The unrequested result requires the host to emit that call after `list_pending`, and that call was not observed.

Boundary: stored page text returned by `list_pending`, and a pending row the operator did not name.

Local plan: on a temporary database, add one pending finding, invoke `list_pending`, and confirm the returned finding includes the stored claim, quote, and source URL. Invoke `approve` with that id and no additional field, then confirm the row status is approved and the export text includes the claim. This checks the server path only.

Owner plan: with the operator's real host connected to this MCP server, list pending findings and record whether the host calls `approve` or `discard` for an id the operator did not name after the stored fields are returned. Limit the check to observing that tool call.
