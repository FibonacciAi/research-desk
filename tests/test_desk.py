import csv
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
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
