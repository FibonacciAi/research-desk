# Research Desk architecture (audit run 1)

## Product, principals, and resources

Research Desk 0.1.0 (`research_desk/__init__.py`) is a local research ledger: a person states a goal, an agent drafts findings (claim, http(s) source URL, quote), the person approves or discards each draft, and only approved rows export as SQL or CSV. There are no accounts and no in-product network calls (`SECURITY.md`, `research_desk/api.py` status field `network`).

Principals in source:

- The OS user who launches the CLI or whose host spawns the stdio MCP server (`mcp.json` runs `python3` on `server/mcp_server.py`).
- The MCP client and the model that supplies `tools/call` arguments. Skills tell the model not to approve without an explicit user decision (`skills/review-and-export/SKILL.md`); the server does not receive a separate confirmation token.
- Page content is untrusted data for the agent (`server/mcp_server.py` initialize instructions). The desk stores whatever the caller submits after `check_url`.
- A later consumer of the export file (the user's database client or spreadsheet), which is outside the process.
- Another local OS user is relevant only where file modes or symlink-following writes are weaker than the user's home directory.

Protected resources: the SQLite file (`desk.db`), finding status (pending, approved, discarded), and files named by export `out` / `out_path`.

Comparable baseline, source-grounded: a single-user local note store plus an MCP tool host, not a multi-tenant warehouse. README contrasts Context.dev (fetches the web) with this desk (stores and exports only). Export dialects name Postgres, SQLite, Snowflake, and BigQuery as text targets the user runs elsewhere. Severity is calibrated to a local same-user tool: cross-tenant SaaS impact is out of model unless a local boundary still changes another principal's files or the safety of generated SQL the user is told is escaped.

## Stack and offline limits

Python 3.10+ standard library only. Entrypoints: `bin/research-desk` and `server/mcp_server.py`, both calling `research_desk/api.py` then `research_desk/store.py`. Plugin wiring is `.cursor-plugin/plugin.json` and `mcp.json`. No CI workflows, lockfile, container, or cloud overlay. Offline checks: `python3 -m unittest discover -s tests -t .` and `bash scripts/e2e.sh`, writing only under temp directories or `RESEARCH_DESK_HOME`. This run's sandbox can enforce an empty environment, no external network, a read-only target bind, scratch-only writes, and prlimit/timeout. Warehouse execution (psql, BigQuery, Excel) is not available locally.

## Entry surfaces and source-to-sink paths

1. CLI argv (`bin/research-desk`) and MCP stdio JSON-RPC (`server/mcp_server.py` `main` / `tools/call`) enter `api.*`.
2. `RESEARCH_DESK_HOME`, `XDG_DATA_HOME`, or `--db` select the SQLite path (`store.default_home`, `Desk.__init__`). `Desk` creates the directory with default mkdir mode and connects with `sqlite3`.
3. `add_finding` strips the claim, runs `check_url` (scheme http/https and a netloc only), and inserts a pending row with bound parameters.
4. `approve` / `discard` call `_decide`, which updates only rows still `pending`.
5. `export` reads `approved_rows` only, renders CSV via `csv.DictWriter` or SQL via `to_sql` / `sql_literal` (single quotes doubled; table name matched to `IDENT`; dialect selects type names only). `api.export` optionally `expanduser`s `out`, creates parents, and `write_text`s the document.
6. `load_demo` reads the fixed file `examples/harborline/goal.json`.

Parallel CLI and MCP paths share those functions. MCP schema checks required and unknown keys only; JSON types and enums are not rechecked in `handle`.

## Trust boundaries and strongest source-visible control

| Boundary | Strongest control in source |
|---|---|
| Who may call tools | None inside the process. Stdio inheritance is the host's. |
| Human approval | Prose in skills and tool descriptions. Code gate is only "status is pending". |
| Export contents | `WHERE status = 'approved'`. |
| SQL text | Identifier regex plus `'` → `''`. Dialect does not change escaping. |
| URL | `urlparse` scheme and netloc. The desk never fetches. |
| Export path | None. Caller path is expanded and written. |
| DB file mode | None beyond process umask and the OS home directory. |

## Starting paths

`server/mcp_server.py`, `bin/research-desk`, `research_desk/api.py`, `research_desk/store.py`, `skills/research-desk/SKILL.md`, `skills/review-and-export/SKILL.md`, `mcp.json`, `.cursor-plugin/plugin.json`, `examples/harborline/goal.json`, `SECURITY.md`, `.gitignore`.

## Prior coverage

No compatible prior ledger or findings file. Every unit is `prior_status: none`. Nothing is hunter-excluded as a carried confirmation.

## Companion selection

Selected because a source-visible boundary matches the companion's "when to use":

- `AI-AND-LLM.md` — MCP server, tool arguments, skill instructions, approval described only in prompts.
- `DATA-ISOLATION-AND-LIFECYCLE.md` — approved-only export, discard retained in the file, demo import.
- `DESKTOP-MOBILE-AND-LOCAL-IPC.md` — stdio local IPC, SQLite path, export file writes.
- `PROTOCOLS-RPC-AND-MESSAGING.md` — newline-delimited JSON-RPC and schema-versus-handler decoding.
- `RESOURCE-EXHAUSTION-AND-AVAILABILITY.md` — unbounded stdin lines into the MCP process (shared-service impact must still be shown).
- `SUPPLY-CHAIN-AND-RELEASE.md` — plugin manifest and shipped skills are the installed artifact; no dependency resolver and no CI are exclusions inside that file, not a reason to skip the plugin boundary.

Not selected: `CLIENT-SIDE.md` (no browser surface), `WEB-PROTOCOL-AND-AUTH.md` (no HTTP service, session, or OAuth), `CLOUD-AND-DEPLOYMENT.md` (no cloud deployment), `MEMORY-SAFETY-AND-BINARY.md` (no native or unsafe parser).
