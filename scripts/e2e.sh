#!/usr/bin/env bash
# End-to-end check on a throwaway database: demo goal -> drafts -> approve/discard -> SQL export -> load into SQLite.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export RESEARCH_DESK_HOME="$TMP/home"
rd() { python3 "$ROOT/bin/research-desk" "$@"; }
rd status >/dev/null
rd demo | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["goal"]["pending"]==5; print("demo: goal", r["goal"]["id"], "with 5 drafts")'
rd list | python3 -c 'import json,sys; r=json.load(sys.stdin); assert len(r["findings"])==5; print("pending:", [f["id"] for f in r["findings"]])'
rd approve 1 3 4 >/dev/null && echo "approved: 1 3 4"
rd discard 2 5 --note "self-reported or unconfirmed" >/dev/null && echo "discarded: 2 5"
rd export --dialect sqlite --out "$TMP/harborline.sql" >/dev/null
sqlite3 "$TMP/check.db" < "$TMP/harborline.sql" 2>/dev/null || python3 -c "import sqlite3,sys; sqlite3.connect('$TMP/check.db').executescript(open('$TMP/harborline.sql').read())"
python3 - "$TMP/check.db" <<'PY'
import sqlite3, sys
rows = sqlite3.connect(sys.argv[1]).execute("SELECT id, source_url FROM research_findings ORDER BY id").fetchall()
assert [r[0] for r in rows] == [1, 3, 4], rows
print("export loaded into SQLite:", len(rows), "rows ->", [r[1] for r in rows])
PY
rd export --format csv | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["rows"]==3; print("csv rows:", r["rows"])'
echo "E2E OK"
