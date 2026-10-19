"""A plain local SQLite store for research goals and findings.

Every finding starts as a draft (status 'pending'). Only a person's explicit
approve moves it to 'approved'; discard moves it to 'discarded'. Exports read
approved findings only. Nothing leaves the machine.
"""
import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  goal_id INTEGER NOT NULL REFERENCES goals(id),
  claim TEXT NOT NULL,
  source_url TEXT NOT NULL,
  quote TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','discarded')),
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  decided_at TEXT
);
"""

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
DIALECTS = {
    "postgres": {"int": "INTEGER", "text": "TEXT"},
    "sqlite": {"int": "INTEGER", "text": "TEXT"},
    "snowflake": {"int": "INTEGER", "text": "TEXT"},
    "bigquery": {"int": "INT64", "text": "STRING"},
}
EXPORT_COLUMNS = ["id", "goal_id", "goal", "claim", "source_url", "quote", "note", "approved_at"]


class DeskError(ValueError):
    """A user-facing error (bad input or a finding in the wrong state)."""


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_home():
    if os.environ.get("RESEARCH_DESK_HOME"):
        return Path(os.environ["RESEARCH_DESK_HOME"]).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "research-desk"


def check_url(url):
    url = (url or "").strip()
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise DeskError(f"source_url must be an http(s) URL, got {url!r}")
    return url


class Desk:
    def __init__(self, db_path=None):
        if db_path is None:
            home = default_home()
            home.mkdir(parents=True, exist_ok=True)
            db_path = home / "desk.db"
        self.path = str(db_path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    # goals
    def start_goal(self, title):
        title = (title or "").strip()
        if not title:
            raise DeskError("goal title is required")
        cur = self.db.execute("INSERT INTO goals (title, created_at) VALUES (?, ?)", (title, now()))
        self.db.commit()
        return self.goal(cur.lastrowid)

    def goal(self, goal_id):
        row = self.db.execute("SELECT * FROM goals WHERE id = ?", (int(goal_id),)).fetchone()
        if not row:
            raise DeskError(f"no goal {goal_id}")
        g = dict(row)
        for status in ("pending", "approved", "discarded"):
            g[status] = self.db.execute("SELECT COUNT(*) FROM findings WHERE goal_id = ? AND status = ?",
                                        (g["id"], status)).fetchone()[0]
        return g

    def list_goals(self):
        return [self.goal(r["id"]) for r in self.db.execute("SELECT id FROM goals ORDER BY id")]

    # findings
    def add_finding(self, goal_id, claim, source_url, quote=""):
        self.goal(goal_id)
        claim = (claim or "").strip()
        if not claim:
            raise DeskError("claim is required")
        cur = self.db.execute(
            "INSERT INTO findings (goal_id, claim, source_url, quote, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(goal_id), claim, check_url(source_url), (quote or "").strip(), now()))
        self.db.commit()
        return self.finding(cur.lastrowid)

    def finding(self, finding_id):
        row = self.db.execute("SELECT * FROM findings WHERE id = ?", (int(finding_id),)).fetchone()
        if not row:
            raise DeskError(f"no finding {finding_id}")
        return dict(row)

    def list_findings(self, goal_id=None, status="pending"):
        q, args = "SELECT * FROM findings WHERE 1=1", []
        if goal_id is not None:
            q += " AND goal_id = ?"
            args.append(int(goal_id))
        if status and status != "all":
            if status not in ("pending", "approved", "discarded"):
                raise DeskError("status must be pending, approved, discarded or all")
            q += " AND status = ?"
            args.append(status)
        return [dict(r) for r in self.db.execute(q + " ORDER BY id", args)]

    def _decide(self, finding_id, status, note=""):
        f = self.finding(finding_id)
        if f["status"] != "pending":
            raise DeskError(f"finding {finding_id} is already {f['status']}")
        self.db.execute("UPDATE findings SET status = ?, note = ?, decided_at = ? WHERE id = ?",
                        (status, (note or "").strip(), now(), int(finding_id)))
        self.db.commit()
        return self.finding(finding_id)

    def approve(self, finding_id, note=""):
        return self._decide(finding_id, "approved", note)

    def discard(self, finding_id, note=""):
        return self._decide(finding_id, "discarded", note)

    # export
    def approved_rows(self, goal_id=None):
        q = ("SELECT f.id, f.goal_id, g.title AS goal, f.claim, f.source_url, f.quote, f.note, f.decided_at AS approved_at "
             "FROM findings f JOIN goals g ON g.id = f.goal_id WHERE f.status = 'approved'")
        args = []
        if goal_id is not None:
            self.goal(goal_id)
            q += " AND f.goal_id = ?"
            args.append(int(goal_id))
        return [dict(r) for r in self.db.execute(q + " ORDER BY f.id", args)]

    def export(self, goal_id=None, fmt="sql", table="research_findings", dialect="postgres"):
        rows = self.approved_rows(goal_id)
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
            return {"format": "csv", "rows": len(rows), "text": buf.getvalue()}
        if fmt != "sql":
            raise DeskError("format must be sql or csv")
        return {"format": "sql", "dialect": dialect, "table": table, "rows": len(rows),
                "text": to_sql(rows, table, dialect)}


def sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def to_sql(rows, table="research_findings", dialect="postgres"):
    if not IDENT.match(table or ""):
        raise DeskError("table must be a plain identifier (letters, digits, underscore)")
    if dialect not in DIALECTS:
        raise DeskError("dialect must be one of: " + ", ".join(DIALECTS))
    t = DIALECTS[dialect]
    types = {"id": t["int"], "goal_id": t["int"]}
    cols = ",\n".join(f"  {c} {types.get(c, t['text'])}{' NOT NULL' if c in ('id', 'claim', 'source_url') else ''}"
                      for c in EXPORT_COLUMNS)
    out = [f"-- Research Desk export: {len(rows)} approved finding(s). Discarded and pending drafts are not included.",
           f"CREATE TABLE IF NOT EXISTS {table} (\n{cols}\n);"]
    for r in rows:
        vals = ", ".join(sql_literal(r[c]) for c in EXPORT_COLUMNS)
        out.append(f"INSERT INTO {table} ({', '.join(EXPORT_COLUMNS)}) VALUES ({vals});")
    return "\n".join(out) + "\n"


def load_demo(desk, path):
    """Load a demo goal file: {"goal": str, "findings": [{claim, source_url, quote}]} as drafts."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    g = desk.start_goal(data["goal"])
    ids = [desk.add_finding(g["id"], f["claim"], f["source_url"], f.get("quote", ""))["id"] for f in data["findings"]]
    return {"goal": desk.goal(g["id"]), "finding_ids": ids}
