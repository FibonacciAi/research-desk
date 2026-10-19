import csv
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_desk import api, store  # noqa: E402
from research_desk.store import Desk, DeskError  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "desk.db")
        self.d = Desk(self.db)

    def tearDown(self):
        self.d.close()
        self.tmp.cleanup()

    def test_goal_and_drafts_start_pending(self):
        g = self.d.start_goal("  What is X?  ")
        self.assertEqual(g["title"], "What is X?")
        f = self.d.add_finding(g["id"], "X is Y.", "https://a.example/x", "X is Y")
        self.assertEqual(f["status"], "pending")
        self.assertEqual(self.d.goal(g["id"])["pending"], 1)

    def test_rejects_bad_input(self):
        g = self.d.start_goal("goal")
        for url in ("ftp://a.example/x", "javascript:alert(1)", "not a url", ""):
            with self.assertRaises(DeskError):
                self.d.add_finding(g["id"], "claim", url)
        with self.assertRaises(DeskError):
            self.d.add_finding(g["id"], "  ", "https://a.example")
        with self.assertRaises(DeskError):
            self.d.add_finding(999, "claim", "https://a.example")
        with self.assertRaises(DeskError):
            self.d.start_goal("")

    def test_decisions_are_final(self):
        g = self.d.start_goal("goal")
        a = self.d.add_finding(g["id"], "a", "https://a.example")
        b = self.d.add_finding(g["id"], "b", "https://b.example")
        self.assertEqual(self.d.approve(a["id"], "ok")["status"], "approved")
        self.assertEqual(self.d.discard(b["id"])["status"], "discarded")
        with self.assertRaises(DeskError):
            self.d.discard(a["id"])
        with self.assertRaises(DeskError):
            self.d.approve(b["id"])
        self.assertEqual(self.d.list_findings(status="pending"), [])

    def test_two_connections_discard_then_approve_stays_discarded(self):
        # Pause the approve connection after it has started _decide and before
        # its UPDATE runs, then discard from a second connection. A sequential
        # discard-then-approve on one connection already raises, and would not
        # catch an UPDATE that ignores status.
        g = self.d.start_goal("goal")
        finding = self.d.add_finding(g["id"], "contested claim", "https://a.example/race", "q")
        fid = finding["id"]
        discarder = Desk(self.db)
        discarder.db.execute("PRAGMA busy_timeout = 2000")
        reached = threading.Event()
        release = threading.Event()
        errors = {}

        def run_approve():
            # Own connection, created on this thread. Its UPDATE waits until
            # the other connection has discarded and committed.
            approver = Desk(self.db)
            approver.db.execute("PRAGMA busy_timeout = 2000")
            real_db = approver.db

            class _PauseBeforeDecision:
                def execute(self, sql, *args, **kwargs):
                    if isinstance(sql, str) and sql.startswith("UPDATE findings SET status"):
                        reached.set()
                        if not release.wait(5):
                            raise TimeoutError("approve was not released")
                    return real_db.execute(sql, *args, **kwargs)

                def __getattr__(self, name):
                    return getattr(real_db, name)

            approver.db = _PauseBeforeDecision()
            try:
                approver.approve(fid, "late")
            except DeskError as exc:
                errors["approve"] = str(exc)
            finally:
                approver.db = real_db
                approver.close()

        worker = threading.Thread(target=run_approve)
        try:
            worker.start()
            self.assertTrue(reached.wait(5), "approve never reached its UPDATE")
            self.assertEqual(discarder.discard(fid, "no")["status"], "discarded")
            release.set()
            worker.join(5)
            self.assertFalse(worker.is_alive())
        finally:
            release.set()
            worker.join(5)
            discarder.close()

        self.assertEqual(errors.get("approve"), f"finding {fid} is already discarded")
        self.assertEqual(self.d.finding(fid)["status"], "discarded")
        self.assertEqual(self.d.approved_rows(), [])
        exported = self.d.export()["text"]
        self.assertNotIn("contested claim", exported)
        self.assertNotIn("INSERT INTO", exported)
        with self.assertRaises(DeskError) as missing:
            self.d.approve(999)
        self.assertEqual(str(missing.exception), "no finding 999")

    def test_export_only_approved_and_sql_runs(self):
        g = self.d.start_goal("Bob's goal")
        a = self.d.add_finding(g["id"], "It's 'quoted'; DROP TABLE x; --", "https://a.example/?q=1&r=2", "line1\nline2")
        b = self.d.add_finding(g["id"], "discard me", "https://b.example")
        self.d.add_finding(g["id"], "leave pending", "https://c.example")
        self.d.approve(a["id"])
        self.d.discard(b["id"])
        sql = self.d.export(fmt="sql", dialect="sqlite")["text"]
        self.assertIn("CREATE TABLE IF NOT EXISTS research_findings", sql)
        self.assertNotIn("discard me", sql)
        self.assertNotIn("leave pending", sql)
        target = sqlite3.connect(":memory:")
        target.executescript(sql)
        rows = target.execute("SELECT id, goal, claim, source_url, quote FROM research_findings").fetchall()
        self.assertEqual(rows, [(a["id"], "Bob's goal", "It's 'quoted'; DROP TABLE x; --", "https://a.example/?q=1&r=2", "line1\nline2")])
        target.executescript(sql)  # idempotent table creation; inserts again
        self.assertEqual(target.execute("SELECT COUNT(*) FROM research_findings").fetchone()[0], 2)

    def test_export_csv_and_options(self):
        g = self.d.start_goal("g")
        f = self.d.add_finding(g["id"], "c, with comma", "https://a.example")
        self.d.approve(f["id"])
        res = self.d.export(fmt="csv")
        rows = list(csv.DictReader(io.StringIO(res["text"])))
        self.assertEqual(rows[0]["claim"], "c, with comma")
        self.assertEqual(list(rows[0].keys()), store.EXPORT_COLUMNS)
        self.assertIn("STRING", self.d.export(dialect="bigquery")["text"])
        self.assertIn("CREATE TABLE IF NOT EXISTS my_tbl", self.d.export(table="my_tbl")["text"])
        for bad in ("x; drop", "1abc", "a-b", ""):
            with self.assertRaises(DeskError):
                self.d.export(table=bad)
        with self.assertRaises(DeskError):
            self.d.export(dialect="oracle")
        with self.assertRaises(DeskError):
            self.d.export(fmt="xml")

    def test_export_scoped_to_goal(self):
        g1, g2 = self.d.start_goal("one"), self.d.start_goal("two")
        for g in (g1, g2):
            self.d.approve(self.d.add_finding(g["id"], "f" + g["title"], "https://a.example")["id"])
        self.assertEqual(self.d.export(goal_id=g2["id"])["rows"], 1)
        self.assertEqual(self.d.export()["rows"], 2)


def _decode_snowflake(literal):
    """One single-quoted Snowflake literal, per the string-constant docs."""
    if not literal.startswith("'"):
        raise AssertionError(literal)
    i, out = 1, []
    simple = {"'": "'", '"': '"', "\\": "\\", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "0": "\0"}
    while i < len(literal):
        ch = literal[i]
        if ch == "'":
            if i + 1 < len(literal) and literal[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), literal[i + 1:]
        if ch == "\\":
            nxt = literal[i + 1]
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            if nxt == "u":
                out.append(chr(int(literal[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(nxt)  # a backslash outside the documented table is ignored
            i += 2
            continue
        if ch == "\n":
            raise AssertionError("raw newline in a Snowflake literal")
        out.append(ch)
        i += 1
    raise AssertionError("unterminated Snowflake literal")


def _decode_bigquery(literal):
    """One single-quoted BigQuery literal. '' is not an escaped quote."""
    if not literal.startswith("'"):
        raise AssertionError(literal)
    i, out = 1, []
    simple = {
        "a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v",
        "\\": "\\", "?": "?", "'": "'", '"': '"', "`": "`",
    }
    while i < len(literal):
        ch = literal[i]
        if ch == "\n":
            raise AssertionError("raw newline in a BigQuery quoted string")
        if ch == "'":
            return "".join(out), literal[i + 1:]
        if ch == "\\":
            nxt = literal[i + 1]
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            if nxt == "u":
                out.append(chr(int(literal[i + 2:i + 6], 16)))
                i += 6
                continue
            if nxt == "U":
                out.append(chr(int(literal[i + 2:i + 10], 16)))
                i += 10
                continue
            if nxt in ("x", "X"):
                out.append(chr(int(literal[i + 2:i + 4], 16)))
                i += 4
                continue
            if nxt in "01234567":
                out.append(chr(int(literal[i + 1:i + 4], 8)))
                i += 4
                continue
            raise AssertionError("unknown BigQuery escape \\" + nxt)
        out.append(ch)
        i += 1
    raise AssertionError("unterminated BigQuery literal")


class SqlLiteralTests(unittest.TestCase):
    PAYLOADS = [
        "",
        "plain",
        "it's",
        "a\\b",
        "end\\",
        "\\z",
        "\\x41",
        "\\n",
        "line1\nline2",
        "tab\there",
        "cr\rhere",
        "nul\0here",
        "\0" + "12",
        "\\\n",
        "bell\ahere",
        "vt\vhere",
        "snowman \u26c4",
        "quotes '''",
        "x\\', CODE_POINTS_TO_STRING([65]), NULL, NULL, NULL); SELECT 1; --",
    ]

    def test_postgres_and_sqlite_only_double_quotes(self):
        for dialect in ("postgres", "sqlite"):
            self.assertEqual(store.sql_literal(None, dialect), "NULL")
            self.assertEqual(store.sql_literal(3, dialect), "3")
            self.assertEqual(store.sql_literal("it's", dialect), "'it''s'")
            self.assertEqual(store.sql_literal("a\\b", dialect), "'a\\b'")
            self.assertEqual(store.sql_literal("line1\nline2", dialect), "'line1\nline2'")
            escaped = store.sql_literal(self.PAYLOADS[-1], dialect)
            self.assertIn("SELECT 1; --", escaped)
            self.assertTrue(escaped.endswith("'"))

    def test_snowflake_and_bigquery_round_trip_documented_lexers(self):
        decoders = {"snowflake": _decode_snowflake, "bigquery": _decode_bigquery}
        for dialect, decode in decoders.items():
            for value in self.PAYLOADS:
                literal = store.sql_literal(value, dialect)
                decoded, rest = decode(literal)
                self.assertEqual(rest, "", (dialect, value, literal, rest))
                self.assertEqual(decoded, value, (dialect, value, literal))
                self.assertNotIn("\n", literal)

    def test_bigquery_quote_and_newline_bytes(self):
        self.assertEqual(store.sql_literal("it's", "bigquery"), "'it\\'s'")
        self.assertEqual(store.sql_literal("line1\nline2", "bigquery"), "'line1\\nline2'")
        self.assertEqual(store.sql_literal("a\\b", "bigquery"), "'a\\\\b'")
        self.assertEqual(store.sql_literal("end\\", "snowflake"), "'end\\\\'")
        self.assertEqual(store.sql_literal("it's", "snowflake"), "'it''s'")
        # \0 would be read as octal and swallow the following digits.
        self.assertEqual(store.sql_literal("\0" + "12", "snowflake"), "'\\u000012'")
        self.assertEqual(store.sql_literal("\0" + "12", "bigquery"), "'\\u000012'")

    def test_export_backslash_quote_is_one_sqlite_column(self):
        quote = self.PAYLOADS[-1]
        with tempfile.TemporaryDirectory() as tmp:
            desk = Desk(os.path.join(tmp, "d.db"))
            try:
                g = desk.start_goal("g")
                fid = desk.add_finding(g["id"], "claim", "https://a.example", quote)["id"]
                desk.approve(fid)
                sql = desk.export(dialect="sqlite")["text"]
                target = sqlite3.connect(":memory:")
                target.executescript(sql)
                stored = target.execute("SELECT quote FROM research_findings").fetchone()[0]
                self.assertEqual(stored, quote)
                for dialect, decode in (("snowflake", _decode_snowflake), ("bigquery", _decode_bigquery)):
                    text = desk.export(dialect=dialect)["text"]
                    literal = store.sql_literal(quote, dialect)
                    self.assertIn(literal, text)
                    self.assertEqual(decode(literal), (quote, ""))
            finally:
                desk.close()


class DemoAndApiTests(unittest.TestCase):
    def test_harborline_demo_is_fictional_and_loads(self):
        data = json.loads(api.DEMO.read_text())
        for f in data["findings"]:
            self.assertTrue(f["source_url"].split("/")[2].endswith(".example"))
        with tempfile.TemporaryDirectory() as t:
            db = os.path.join(t, "d.db")
            r = api.demo(db)
            self.assertEqual(r["goal"]["pending"], 5)
            api.approve([1, 3, 4], db=db)
            api.discard([2, 5], "rumor", db=db)
            out = os.path.join(t, "out", "h.sql")
            e = api.export(out=out, db=db)
            self.assertEqual(e["rows"], 3)
            self.assertTrue(Path(out).read_text().startswith("-- Research Desk export: 3"))
            s = api.status(db)
            self.assertEqual((s["approved"], s["discarded"], s["pending"], s["plan"]), (3, 2, 0, "free"))
            self.assertEqual(len(s["skills"]), 2)

    def test_env_home(self):
        with tempfile.TemporaryDirectory() as t:
            old = os.environ.get("RESEARCH_DESK_HOME")
            os.environ["RESEARCH_DESK_HOME"] = t
            try:
                self.assertEqual(api.status()["db"], os.path.join(t, "desk.db"))
            finally:
                if old is None:
                    os.environ.pop("RESEARCH_DESK_HOME")
                else:
                    os.environ["RESEARCH_DESK_HOME"] = old


class CliTests(unittest.TestCase):
    def run_cli(self, db, *args):
        p = subprocess.run([sys.executable, str(ROOT / "bin" / "research-desk"), "--db", db, *args],
                           capture_output=True, text=True, timeout=30)
        return p.returncode, json.loads(p.stdout)

    def test_cli_flow(self):
        with tempfile.TemporaryDirectory() as t:
            db = os.path.join(t, "d.db")
            rc, r = self.run_cli(db, "start-goal", "Test goal")
            self.assertEqual((rc, r["goal"]["id"]), (0, 1))
            rc, r = self.run_cli(db, "add-finding", "1", "A claim", "https://a.example/p", "--quote", "q")
            self.assertEqual(r["finding"]["status"], "pending")
            rc, r = self.run_cli(db, "add-finding", "1", "Bad", "file:///etc/passwd")
            self.assertEqual((rc, r["ok"]), (2, False))
            self.assertEqual(self.run_cli(db, "approve", "1")[1]["approved"][0]["status"], "approved")
            rc, r = self.run_cli(db, "approve", "1")
            self.assertEqual(rc, 2)
            rc, r = self.run_cli(db, "export", "--format", "csv")
            self.assertIn("A claim", r["text"])


class McpTests(unittest.TestCase):
    def test_stdio_protocol(self):
        with tempfile.TemporaryDirectory() as t:
            env = {**os.environ, "RESEARCH_DESK_HOME": t}
            msgs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "start_goal", "arguments": {"title": "G"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "add_finding", "arguments": {"goal_id": 1, "claim": "C", "source_url": "https://a.example"}}},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "approve", "arguments": {"finding_ids": [1]}}},
                {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "export_sql", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "approve", "arguments": {"finding_ids": [1]}}},
                {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "approve", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 9, "method": "nope"},
            ]
            p = subprocess.run([sys.executable, str(ROOT / "server" / "mcp_server.py")], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                               capture_output=True, text=True, env=env, timeout=30)
            out = {r["id"]: r for r in map(json.loads, p.stdout.splitlines())}
            self.assertEqual(sorted(out), [1, 2, 3, 4, 5, 6, 7, 8, 9])
            self.assertEqual(out[1]["result"]["serverInfo"]["name"], "research-desk")
            names = {t["name"] for t in out[2]["result"]["tools"]}
            self.assertEqual(names, {"research_desk_status", "start_goal", "list_goals", "add_finding", "list_pending",
                                     "approve", "discard", "export_sql", "load_demo"})
            self.assertEqual(out[6]["result"]["structuredContent"]["rows"], 1)
            self.assertTrue(out[7]["result"]["isError"])
            self.assertTrue(out[8]["result"]["isError"])
            self.assertEqual(out[9]["error"]["code"], -32601)


class ManifestTests(unittest.TestCase):
    def test_manifest_paths_exist(self):
        m = json.loads((ROOT / ".cursor-plugin" / "plugin.json").read_text())
        for k in ("logo", "mcpServers", "skills"):
            self.assertTrue((ROOT / m[k]).exists(), k)
        mcp = json.loads((ROOT / "mcp.json").read_text())["mcpServers"]["research-desk"]
        self.assertEqual(mcp["args"], ["${CURSOR_PLUGIN_ROOT}/server/mcp_server.py"])
        for s in (ROOT / "skills").glob("*/SKILL.md"):
            head = s.read_text().split("---")[1]
            self.assertIn("name: " + s.parent.name, head)
            self.assertIn("description:", head)


if __name__ == "__main__":
    unittest.main()
