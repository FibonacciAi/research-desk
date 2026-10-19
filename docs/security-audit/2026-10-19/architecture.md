# Research Desk architecture (audit run 2026-10-19)

## Product and principals

Research Desk 0.1.0 is a local research ledger. The operator names a goal and sources. An agent drafts findings (claim, http(s) URL, verbatim quote). The operator is supposed to approve or discard each draft. Only approved rows export as SQL or CSV. Data stays in one SQLite file. The process makes no network calls and has no accounts.

The operator is the OS user who runs the CLI or the MCP host. The MCP client and the CLI are that same user: stdio JSON-RPC and argv have no peer identity. Web-page authors are lower trust only after an agent copies their text into `claim`, `quote`, `source_url`, or `note`. Other local OS users are a separate principal for files the process creates or opens. The SQL warehouse or spreadsheet that later runs an export is a downstream consumer, not a principal of this process.

Protected resources are the SQLite file, the export text, and any filesystem path `export` writes. The product promise that matters here is in `SECURITY.md` and the README: table names are plain identifiers, values are SQL string literals, pending and discarded drafts are not exported, and approval is an explicit human decision. The human-decision rule is written in skills and tool descriptions. `approve` does not check it.

## Comparable baseline

Local documentation compares the product with Context.dev (web fetch stays in the agent) and with Postgres, SQLite, Snowflake, BigQuery, and spreadsheets as export consumers. The security trade-off those local MCP ledgers accept is that the process uid is the authority boundary and prompt text is not an enforcement point. That calibrates severity. It does not excuse a broken export encoding or a filesystem write that follows a symlink.

## Stack and offline limits

Python 3.10+ standard library only. No package manifest, lockfile, container, or CI workflow. Entry points are `bin/research-desk` and `server/mcp_server.py` (stdio JSON-RPC, launched from `mcp.json`). Both call `research_desk/api.py`, which calls `research_desk/store.py`. Plugin metadata is `.cursor-plugin/plugin.json`. Tests are `python3 -m unittest discover -s tests -t .` and `bash scripts/e2e.sh`, using temp directories.

Parent-run checks can use a user, mount, pid, and net namespace with a read-only target and toolchain, an empty allowlisted environment, scratch-only writes, and low ulimits. Hunters do not execute the product. There is no BigQuery, Snowflake, spreadsheet, or second OS account in this sandbox.

## Entry surfaces and source-to-sink paths

1. MCP `tools/call` (`server/mcp_server.py`) checks required and extra keys, then calls `api.*`.
2. CLI argparse (`bin/research-desk`) calls the same `api.*` functions, plus `--db`.
3. `RESEARCH_DESK_HOME`, `XDG_DATA_HOME`, and `Path.home()` select `desk.db` when `--db` is omitted. MCP cannot pass a db path.
4. `load_demo` reads only `examples/harborline/goal.json`.
5. Stored rows are copied to MCP/CLI JSON, to `to_sql` / CSV, and, if `out` or `out_path` is set, to `Path.write_text`.

Local queries are parameterized. Export identifiers go through `IDENT`. Export values go through `sql_literal`, which quotes strings and doubles single quotes for every dialect. Dialect choice changes column types only. CSV uses `csv.DictWriter` with no formula prefix. `api.export` expands `~`, creates parent directories, and writes the path it was given. `check_url` requires an http(s) scheme and a netloc and does not fetch.

## Trust boundaries and strongest source-visible control

| Boundary | Strongest control in source |
|---|---|
| MCP/CLI caller to SQLite mutations | None. Any stdin or argv caller has the process uid. Finding updates are parameterized and pending-only. |
| Approval as a human decision | Skill and tool description text only. |
| Export includes only approved rows | `approved_rows` filters `status = 'approved'`. |
| Export SQL shape | `IDENT` on the table; `sql_literal` on values; dialect allowlist. |
| Export file path | No root, no `O_NOFOLLOW`, no mode. |
| `source_url` | Scheme and netloc check. No outbound request exists. |
| Web content in the model | Instruction string. Quotes are returned verbatim by `list_pending`. |

## Starting paths

`server/mcp_server.py`, `bin/research-desk`, `research_desk/api.py`, `research_desk/store.py`, `skills/research-desk/SKILL.md`, `skills/review-and-export/SKILL.md`, `examples/harborline/goal.json`, `tests/test_desk.py`, `SECURITY.md`, `mcp.json`, `.cursor-plugin/plugin.json`.

## Prior coverage

No prior `coverage-ledger.json` or `findings.json` was found. Every unit is `prior_status: none`. Nothing is excluded as a carried same-source confirmation.

## Companion selection

Selected because the matching boundary is in source:

- `AI-AND-LLM.md` — MCP tool arguments, approval instructions, and stored quotes returned to the model.
- `DATA-ISOLATION-AND-LIFECYCLE.md` — approved-only export and the pending/discarded lifecycle.
- `PROTOCOLS-RPC-AND-MESSAGING.md` — newline JSON-RPC and schema-versus-handler checks.
- `RESOURCE-EXHAUSTION-AND-AVAILABILITY.md` — unbounded title, claim, quote, and note text into the local database.
- `SUPPLY-CHAIN-AND-RELEASE.md` — plugin manifest and stdlib-only release inputs.

Not selected, with the source fact: `WEB-PROTOCOL-AND-AUTH.md` (no HTTP server or session), `CLIENT-SIDE.md` (no DOM; `assets/logo.svg` is a static logo), `CLOUD-AND-DEPLOYMENT.md` (no IAM or deploy manifests), `MEMORY-SAFETY-AND-BINARY.md` (no native parser), `DESKTOP-MOBILE-AND-LOCAL-IPC.md` (no socket, deep link, or helper; stdio MCP is covered as JSON-RPC and tool dispatch).
