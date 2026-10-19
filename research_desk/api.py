"""Actions shared by the CLI and the MCP server. Each returns a JSON-serializable dict."""
from pathlib import Path

from . import VERSION
from .store import Desk, DeskError, load_demo

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "harborline" / "goal.json"


def _with(fn, db=None):
    desk = Desk(db)
    try:
        return fn(desk)
    finally:
        desk.close()


def status(db=None):
    def f(d):
        return {"name": "Research Desk", "version": VERSION, "plan": "free", "db": d.path,
                "skills": sorted(str(p.relative_to(ROOT)) for p in (ROOT / "skills").glob("*/SKILL.md")),
                "goals": len(d.list_goals()),
                "pending": len(d.list_findings(status="pending")),
                "approved": len(d.list_findings(status="approved")),
                "discarded": len(d.list_findings(status="discarded")),
                "network": "none (the desk stores and exports only; your agent does the reading)"}
    return _with(f, db)


def start_goal(title, db=None):
    return _with(lambda d: {"goal": d.start_goal(title)}, db)


def list_goals(db=None):
    return _with(lambda d: {"goals": d.list_goals()}, db)


def add_finding(goal_id, claim, source_url, quote="", db=None):
    return _with(lambda d: {"finding": d.add_finding(goal_id, claim, source_url, quote)}, db)


def list_findings(goal_id=None, status="pending", db=None):
    return _with(lambda d: {"status": status, "findings": d.list_findings(goal_id, status)}, db)


def approve(finding_ids, note="", db=None):
    return _with(lambda d: {"approved": [d.approve(i, note) for i in _ids(finding_ids)]}, db)


def discard(finding_ids, note="", db=None):
    return _with(lambda d: {"discarded": [d.discard(i, note) for i in _ids(finding_ids)]}, db)


def export(goal_id=None, fmt="sql", table="research_findings", dialect="postgres", out=None, db=None):
    res = _with(lambda d: d.export(goal_id, fmt, table, dialect), db)
    if out:
        p = Path(out).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(res["text"], encoding="utf-8")
        res["path"] = str(p)
    return res


def demo(db=None):
    return _with(lambda d: load_demo(d, DEMO), db)


def _ids(v):
    if isinstance(v, (int, str)):
        v = [v]
    out = []
    for x in v:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            raise DeskError(f"finding id must be a number, got {x!r}")
    if not out:
        raise DeskError("give at least one finding id")
    return out


__all__ = ["DeskError", "status", "start_goal", "list_goals", "add_finding", "list_findings",
           "approve", "discard", "export", "demo"]
