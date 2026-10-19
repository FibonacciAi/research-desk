# Needs validation

These leads are source-grounded and unresolved. They are not confirmed vulnerabilities and they have no severity.

## SQL export encodes every dialect with quote-doubling only

- **Fingerprint:** `store.sql_literal.quote-doubling-only`
- **Boundary:** Approved finding text becomes an `INSERT` literal. The product says every value is escaped as a SQL string literal and that `dialect` changes column types only (`SECURITY.md`, `README.md`).
- **Claimed cause:** `sql_literal` is the only string encoder. It doubles single quotes and copies backslashes unchanged. `to_sql` uses it for `postgres`, `sqlite`, `snowflake`, and `bigquery`.

### Trace

1. **Entrypoint.** `server/mcp_server.py` `handle` (line 67) accepts `add_finding` claim, source URL, and quote with no character allowlist. The CLI `add-finding` path reaches the same `api.add_finding` function.
2. **Propagation.** `call` (line 43) forwards those fields. `Desk.add_finding` (line 111) stores them with bound parameters. `approved_rows` (line 152) later selects the approved strings without rewriting them. `to_sql` (line 195) passes every export column through `sql_literal`.
3. **Sink.** `sql_literal` (line 180) returns a single-quoted literal whose only change is `'` to `''`.

### Evidence checked

- `DIALECTS` in `research_desk/store.py` (line 37) maps dialects to type names only.
- `check_url` (line 64) accepts an `http(s)` URL whose path contains a backslash and a quote.
- A scratch MCP export of the quote whose characters are `x`, backslash, quote, comma, space, `CODE_POINTS_TO_STRING([65]), NULL, NULL, NULL); SELECT 1; --` produced the same `INSERT` line for all four dialects. Python `sqlite3` 3.45.1 `executescript` stored that quote as one column equal to the submitted payload and did not run `SELECT 1`.
- `psql`, a Snowflake client, and `bq` are not installed. BigQuery, Snowflake, and Postgres did not run.

### Blockers

- The only SQL engine executed was Python's `sqlite3`. Passing that replay does not decide the other dialects.
- Whether the quote literal is one string or a statement boundary depends on each named dialect's string lexer. Those lexers are outside the sandbox.

### Resolution

**Local (done for SQLite):** Call `export_sql` with no output path for each dialect, compare the `INSERT` lines, and run the SQLite text with `sqlite3.connect(":memory:").executescript`. This run already saw identical `INSERT` lines and a single SQLite column equal to the payload.

**Owner-observed:** In a new empty disposable database that contains no other objects, load one approved finding with source URL `https://a.example/p` and the quote above. Run that unchanged export text once in BigQuery standard SQL, once in Snowflake, and once in Postgres. Read the quote column and record whether it equals the submitted payload and whether any statement besides the `CREATE` and the single `INSERT` ran. On Postgres, record `standard_conforming_strings` and repeat in that same empty database with the setting on and off. Stop after those reads. Do not point the script at a populated warehouse.

If a dialect treats the backslash-quote sequence as the end of the literal, the source change is a per-dialect encoder, with a regression that this payload round-trips as one value.
