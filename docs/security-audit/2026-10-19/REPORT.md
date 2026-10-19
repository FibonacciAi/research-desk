# Research Desk security audit — 2026-10-19

## Run

| Item | Value |
|---|---|
| Profile | standard (full repository, not a scoped or quick pass) |
| Budget | none |
| Source | `0faecdf3a417e29194f1505e5a7b51b9d421dcbf` (worktree clean at start; product source unchanged) |
| Execution | sandboxed source and local fixtures only |
| Prior runs | none |

Agents spent: 4 reconnaissance, 4 hunters in one wave (4 planned), 1 post-wave critic plus one follow-up that withdrew its reassignments, 1 final coverage critic, 4 candidate verifiers, and 4 final record verifiers. No cap was set, so the critic and both verifier passes ran.

The sandbox was a user, mount, pid, and net namespace with no external route, an empty allowlisted environment, a read-only target and toolchain, scratch-only writes, and low CPU, file-size, and wall-clock limits. Hunters did not execute the product. Parent-side sandbox runs produced the three promoted `boundary-report.json` files cited by the open leads. No BigQuery, spreadsheet, or second OS account was available.

No prior `coverage-ledger.json` or `findings.json` exists. Nothing was carried as a same-source confirmation.

Out of scope by source absence: HTTP sessions, browser DOM, cloud IAM, native memory safety, and local IPC other than stdio JSON-RPC. No x402 or payment code is in this tree. No unit was deferred.

## Posture

Research Desk 0.1.0 is a local SQLite ledger. The CLI and the stdio MCP server are the same OS user. Local inserts and updates are parameterized, exports keep only `status = 'approved'`, table names must match `IDENT`, and `check_url` does not fetch. This pass confirmed no vulnerability. Four source-grounded leads stay open because the decisive fact is a host model, a spreadsheet, a second local account, or a BigQuery lexer, none of which is in the repository.

## Confirmed findings

No confirmed findings.

| Severity | Title | Boundary | Observed result |
|---|---|---|---|
| — | None | — | — |

## NEEDS VALIDATION

These are not confirmed vulnerabilities and have no severity. Detail is in `NEEDS-VALIDATION.md`.

| Title | Trace | Blocker | Local next step | Owner check |
|---|---|---|---|---|
| Default research database is created without a private file mode | `server/mcp_server.py` `call` → `Desk.__init__` `sqlite3.connect` | Sandbox recorded directory `0o755` and `desk.db` `0o644` under umask 022. No second account opened the file. Real home mode was not measured. | Disposable two-uid fixture, parents `0700` and `0755`, empty databases, operator home untouched. | `stat` the home, `.local/share`, and `XDG_DATA_HOME` or `RESEARCH_DESK_HOME` chain. Do not print database contents. |
| Approved CSV export emits a claim that starts with equals and has no formula prefix | `add_finding` → `Desk.export` `csv.DictWriter` | Unquoted claim cell `=1+1` was written. Spreadsheet formula selection was not run. | Repeat the CSV export on a temporary desk and confirm the cell text. Do not open a spreadsheet. | On the operator's computer, open that file in the spreadsheet already used for exports and record whether the cell is calculated. |
| BigQuery export reuses apostrophe-only SQL quoting | `add_finding` → `to_sql` `sql_literal` | Encoder bytes are recorded. No BigQuery lexer is in the repo, so a complete token, a syntax error, and an early end of the same INSERT are undistinguished. | Classify the three spellings already emitted, with a lexer that is already on local disk. | Throwaway empty dataset only. Record a syntax error, a cell equal to the original characters, or an early end of that same INSERT. |
| Approve and discard commit pending ids with no stored user decision | `list_pending` → `Desk._decide` | The server updates any still-pending id. Whether stored quote text causes a host to call `approve` for an id the operator did not name was not observed. | Temporary database: `list_pending` returns claim, quote, and URL; `approve` then marks that id approved. Server path only. | With the real host, record whether it calls `approve` or `discard` for an id the operator did not name. |

## Hardening and positive controls

- `api.export` expands `~`, creates parents, and `write_text`s the given path with no root, `O_NOFOLLOW`, or mode. A parent-side sandbox saw that write follow a final symlink and replace a dummy file the same uid could already write. Writing the caller-supplied path is the contract. A different local user can plant that symlink only in a parent they can already write.
- Product modules do not call a shell, `eval`, `exec`, or a network client. `subprocess` appears only in tests, as an argument list. Skill shell examples are host instructions.
- No tracked password, token, or private key. The contact address in `SECURITY.md` is public.
- `approved_rows` keeps `status = 'approved'`. `_decide` refuses a second decision. Tests expect pending and discarded claims to stay out of the sqlite export, and expect apostrophe, semicolon, and newline text to remain data under `dialect=sqlite`.
- `check_url` accepts any http(s) netloc, including userinfo and loopback, and stores the string. Nothing dereferences it.
- Batch approve commits each id before the next. A later error leaves the earlier requested ids approved. Running an export script twice inserts duplicate rows for the same operator.
- `handle` checks required and extra keys only. Unknown status, format, and dialect are rejected in `store.py`. `int()` coercion does not cross a principal.
- Claim, quote, note, and title have no length cap. The bytes stay in the operator's process and database.
- `python3` on `PATH` is unpinned. There is no in-repo build, lockfile, or CI workflow that consumes a floating ref.
- `load_demo` reads only the fixed `examples/harborline/goal.json`.

## Coverage

| Status | Count |
|---|---|
| Covered | 11 |
| Candidate (all four fingerprints have a final `needs_validation` record) | 6 |
| Blocked | 0 |
| Deferred | 0 |
| Out of scope | 0 |
| Total | 17 |

The post-wave critic first named three reassignments, then withdrew them. No second hunter wave ran. The final critic returned no missing units and no reassignments, and stopped. This pass does not exhaust the target. A later change to `sql_literal`, `Desk.export`, `Desk.__init__`, or `approve` should re-open the linked units.
