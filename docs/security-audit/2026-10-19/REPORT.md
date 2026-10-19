# Research Desk security audit

## Run

| Item | Value |
|---|---|
| Profile | standard, full repository |
| Scope | Entire Research Desk tree at `/workspace` |
| Budget | Not set. Agents used: 4 reconnaissance, 8 hunters, 3 coverage critics, 3 candidate verifiers, 2 record verifiers |
| Source | `0faecdf3a417e29194f1505e5a7b51b9d421dcbf`, clean worktree |
| Execution | Sandboxed source and local fixtures only. Empty environment, no external network, read-only target, scratch-only writes, resource limits. No live host, warehouse, or spreadsheet was contacted |
| Prior runs | None. No compatible coverage ledger or findings file was available |
| Carried confirmations | None |
| Deferred / out of scope | None. Both the post-wave critic and the distinct final-clean critic accepted no missing units and no reassignments |

This is a complete standard pass of the source that is in the repository. It is not a claim that every future change is covered.

## Security posture

Research Desk is a single-user local ledger. The CLI and the stdio MCP server share one SQLite file, store drafts until `approve` or `discard`, and export approved rows as SQL or CSV. The process does not fetch URLs, does not embed credentials, and parameterizes its own SQL. The human-approval rule in the skills is instruction text; the server enforces only that a finding is still `pending`.

One confirmed defect is local to that state machine: the pending check is not the predicate of the update, so two connections can both commit and the later write wins. One lead remains open: string escaping is quote-doubling for every dialect, and only SQLite was executed here. Path writes, list/status tools, the demo import, and the plugin tree did not show a second principal gaining a capability the launching user does not already have.

## Confirmed findings

| Severity | Title | Boundary | Observed result |
|---|---|---|---|
| low | Overlapping approve and discard both commit because the pending check is outside the write | `Desk._decide` status transition | A discard that had committed was replaced by a later approve. The row was approved and appeared in `approved_rows` |

### Overlapping approve and discard both commit because the pending check is outside the write

- **Fingerprint:** `research_desk/store.py:_decide:unconditional-status-update`
- **Location:** `research_desk/store.py` `_decide` (pending read at line 137, id-only `UPDATE` at line 139). Entry from MCP `approve` in `server/mcp_server.py` `call` and from `research_desk/api.py` `approve`.
- **Lower-trust principal:** A second connection to the same database, including an MCP `tools/call` `approve`, overlapping a discard. One MCP stdin loop is serial; the overlap is another process, such as the CLI, on that file.
- **Reproduction:** In a scratch database, create one goal and one pending finding. On two connections, read `status` and record that both are `pending`. Commit `UPDATE findings SET status = 'discarded', note = '', decided_at = '2020-01-01T00:00:00Z' WHERE id = 1`. Then commit `UPDATE findings SET status = 'approved', note = '', decided_at = '2020-01-01T00:00:00Z' WHERE id = 1`. Read `status`, `approved_rows`, and the SQL export.
- **Conditions:** Both reads happen while the row is pending. After the first commit the row is decided, and the second update still matches it by id.
- **Result:** Both reads were pending. The discard update committed with rowcount 1. The approve update then committed with rowcount 1. Final status was `approved`, `approved_rows` was `[1]`, and the export contained the dummy claim. With the same gap inside `api.discard` and `api.approve`, both calls returned success and the stored status was `approved`. A later discard of that approved row on one connection raised `finding 1 is already approved`.
- **Impact:** The database belongs to the OS user who launched the CLI or MCP server. A discard that already committed can still be exported, or an approval can be replaced by a discard. This does not read or write another user's files.
- **Priority:** Low likelihood, because the window is the gap between the `SELECT` and the `UPDATE` and needs two connections. Low impact, because the blast radius is that user's ledger. Overall severity is low.
- **Smallest fix:** Make the transition one `UPDATE` whose `WHERE` includes `id = ? AND status = 'pending'`, and treat rowcount 0 as missing or already decided. A scratch check of that predicate left the row `discarded` when the approve form ran second. Add a regression with two connections that both observe `pending`, one discard commit, and an approve that must not change the row.

## NEEDS VALIDATION

| Title | Trace | Blocker | Local next step | Owner-observed check |
|---|---|---|---|---|
| SQL export encodes every dialect with quote-doubling only | MCP `add_finding` to `sql_literal` | BigQuery, Snowflake, and Postgres lexers were not run | Replay the scratch INSERT in SQLite and confirm one column. Already done for SQLite | In an empty disposable database, run the same export text once per named engine and compare the quote column with the submitted text |

This is not a confirmed vulnerability and has no severity. Detail is in `NEEDS-VALIDATION.md`.

## Hardening and positive patterns

Hardening, not findings:

- `approve` and `discard` advertise `destructiveHint: false`, and the server never reads that hint. The human-decision sentence lives in the skill and the tool description. The caller is the same OS user who can run the CLI. Set `destructiveHint` true so a host can treat the status change as destructive.
- `api.approve` commits inside each id. A list that fails on a later id leaves the earlier ids decided.
- New database and export files take the process umask. Under umask `022` they were mode `0644`, with created directories `0755`. On this host `/home/ubuntu` is mode `0750`, so another local account could not open the default file. Creating `desk.db` and export files as `0600`, and directories this code creates as `0700`, would keep that property when an ancestor is searchable by others. `Path.write_text` follows a symlink at the named path; `O_NOFOLLOW` and `O_EXCL` would refuse a name someone else planted in a sticky directory the caller selected.
- `tools/call` checks required and unknown keys, not JSON types. Numeric and boolean values that `int()` accepts select the same goal or finding the caller can already name, and a falsy status lists every row, which `status: "all"` already allows.
- An unbounded stdin line can terminate the caller's own MCP process. That process is not shared with another principal.
- CSV export copies approved text, including a cell that starts with `=`, `+`, `-`, or `@`. Validation rejected fingerprint `store.export.csv.formula-prefix`: the desk's stated policy is to emit the approved text for the same user to open, and `SECURITY.md` promises SQL literal escaping, not formula neutralization.
- `check_url` accepts any `http` or `https` netloc, including loopback. Nothing in this process fetches or opens that string.

Positive patterns:

- Goal and finding writes use bound parameters. Export selection is `WHERE status = 'approved'`, and scratch exports omitted pending and discarded markers.
- Table names must match `^[A-Za-z_][A-Za-z0-9_]{0,62}$`.
- Quote-doubling kept an apostrophe and the text `DROP TABLE` inside one SQLite column when that dialect's export was executed.
- `load_demo` reads only `examples/harborline/goal.json`. A status field in a scratch document did not approve a row.
- The tree has no committed credential, no `eval` or `exec` of caller input, no HTTP listener, and no CI workflow. Application imports are the Python standard library.

## Coverage

| Status | Units |
|---|---|
| Covered | 20 |
| Candidate | 4 (three fingerprints, all with a final verdict) |
| Blocked | 0 |
| Deferred | 0 |
| Out of scope | 0 |

The four candidate units are the CLI and MCP paths into `sql_literal`, the CSV writer, and `_decide`. Final verdicts: `store.sql_literal.quote-doubling-only` needs validation; `research_desk/store.py:_decide:unconditional-status-update` confirmed; `store.export.csv.formula-prefix` rejected. The final-clean critic returned no further units.
