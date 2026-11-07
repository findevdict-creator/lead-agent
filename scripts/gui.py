#!/usr/bin/env python3
"""Local web GUI for the lead agent. Standard library only, no API keys.

Usage:
  python3 scripts/gui.py [--port 8765] [--no-browser]

Then open http://127.0.0.1:8765. The server only listens on this computer.
Everything it changes goes through scripts/leads.py, so the CLI, the slash
commands and the GUI all share the same files.

The Run page starts agent commands (/find-leads, /harvest, ...) through your
local Claude Code CLI (`claude -p`), so it uses your existing Claude Code login.
Set LEAD_AGENT_CLAUDE to point at a different claude binary.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leads  # noqa: E402

STATIC = Path(__file__).resolve().parent.parent / "gui"
COMMANDS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "commands"
LOCK = threading.RLock()
# Commands that make sense to run unattended from the GUI. /review-leads, /update, /export and
# /pipeline are covered by GUI pages instead.
RUNNABLE = ["find-leads", "harvest", "verify-candidates", "enrich", "more-like", "draft-outreach",
            "digest", "build-icp", "setup-product"]
EDITABLE_DOCS = ("product.md", "icp.md")
READABLE_DOCS = EDITABLE_DOCS + ("searches.log",)
MAX_BODY = 20 * 1024 * 1024


def claude_bin() -> str | None:
    env = os.environ.get("LEAD_AGENT_CLAUDE")
    if env:
        return env
    return shutil.which("claude")


def command_info() -> list[dict]:
    out = []
    for name in RUNNABLE:
        path = COMMANDS_DIR / f"{name}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        desc = re.search(r"^description:\s*(.+)$", text, re.M)
        hint = re.search(r"^argument-hint:\s*(.+)$", text, re.M)
        out.append({"name": name, "description": desc.group(1).strip() if desc else "",
                    "hint": hint.group(1).strip() if hint else ""})
    return out


# ---------- background agent jobs ----------

class Job:
    def __init__(self, command: str, args: str, product: str):
        self.id = uuid.uuid4().hex[:8]
        self.command = command
        self.args = args
        self.product = product
        self.started = time.strftime("%Y-%m-%d %H:%M:%S")
        self.finished = ""
        self.status = "running"
        self.lines: list[str] = []
        self.proc: subprocess.Popen | None = None
        self.cost = None

    def summary(self) -> dict:
        return {"id": self.id, "command": self.command, "args": self.args, "product": self.product,
                "started": self.started, "finished": self.finished, "status": self.status,
                "lines": len(self.lines), "cost": self.cost}


JOBS: dict[str, Job] = {}


def describe_event(ev: dict) -> list[str]:
    """Turn one stream-json event from `claude -p` into readable log lines."""
    t = ev.get("type")
    out = []
    if t == "system" and ev.get("subtype") == "init":
        out.append(f"· session started ({ev.get('model', 'claude')})")
    elif t == "assistant":
        for c in ev.get("message", {}).get("content", []):
            if c.get("type") == "text" and c.get("text", "").strip():
                out.append(c["text"].strip())
            elif c.get("type") == "tool_use":
                inp = c.get("input", {})
                detail = (inp.get("query") or inp.get("url") or inp.get("command") or inp.get("file_path")
                          or inp.get("pattern") or "")
                out.append(f"→ {c.get('name')}: {str(detail)[:200]}")
    elif t == "result":
        if ev.get("is_error"):
            out.append(f"✗ finished with an error: {ev.get('result', '')}")
        else:
            out.append("✓ finished")
    return out


def run_job(job: Job, prompt: str) -> None:
    binary = claude_bin()
    cmd = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "acceptEdits"]
    env = dict(os.environ, LEAD_AGENT_PRODUCT=job.product)
    try:
        job.proc = subprocess.Popen(cmd, cwd=str(leads.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                    env=env)
    except OSError as e:
        job.lines.append(f"could not start claude: {e}")
        job.status = "failed"
        job.finished = time.strftime("%Y-%m-%d %H:%M:%S")
        return
    assert job.proc.stdout is not None
    for raw in job.proc.stdout:
        raw = raw.rstrip("\n")
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            job.lines.append(raw)
            continue
        if ev.get("type") == "result" and ev.get("total_cost_usd") is not None:
            job.cost = ev["total_cost_usd"]
        if ev.get("type") == "result" and ev.get("result"):
            job.lines.append("")
            job.lines.extend(str(ev["result"]).splitlines())
        job.lines.extend(describe_event(ev))
    code = job.proc.wait()
    if job.status == "running":
        job.status = "done" if code == 0 else "failed"
    job.finished = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        log_dir = leads.DATA_ROOT / job.product / "runs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{job.started[:10]}-{job.command}-{job.id}.log").write_text(
            f"/{job.command} {job.args}\nstatus: {job.status}\n\n" + "\n".join(job.lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def start_job(command: str, args: str) -> Job:
    if command == "ask":
        prompt = args
        if not prompt.strip():
            raise ValueError("type a request for the agent")
    elif command in RUNNABLE:
        prompt = f"/{command} {args}".strip()
    else:
        raise ValueError(f"cannot run {command} from the GUI")
    if len(prompt) > 2000:
        raise ValueError("request is too long")
    if not claude_bin():
        raise ValueError("Claude Code CLI not found. Install it, or set LEAD_AGENT_CLAUDE to its path.")
    job = Job(command, args, leads.PRODUCT)
    JOBS[job.id] = job
    threading.Thread(target=run_job, args=(job, prompt), daemon=True).start()
    return job


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "LeadAgentGUI/1.0"

    def log_message(self, fmt, *args):  # quieter console
        if os.environ.get("LEAD_AGENT_GUI_DEBUG"):
            super().log_message(fmt, *args)

    # -- helpers --
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1") or host == self.server.allowed_host

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def error(self, msg: str, code: int = 400) -> None:
        self.json({"error": msg}, code)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def sync_product(self) -> None:
        leads.use_product(leads.active_product())

    # -- routing --
    def do_GET(self):
        if not self._host_ok():
            return self.error("bad host", 403)
        url = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        try:
            with LOCK:
                self.sync_product()
                if url.path.startswith("/api/"):
                    return self.get_api(url.path[5:], q)
            return self.static(url.path)
        except Exception as e:  # keep the server alive and show the error in the UI
            return self.error(f"{type(e).__name__}: {e}", 500)

    def do_POST(self):
        if not self._host_ok():
            return self.error("bad host", 403)
        # A custom header forces a CORS preflight, which this server never approves, so other
        # websites open in your browser cannot post to it.
        if self.headers.get("X-Lead-Agent") != "1":
            return self.error("missing X-Lead-Agent header", 403)
        url = urlparse(self.path)
        try:
            data = self.body()
            with LOCK:
                self.sync_product()
                return self.post_api(url.path[5:], data)
        except KeyError as e:
            return self.error(f"not found: {e.args[0] if e.args else e}", 404)
        except (ValueError, json.JSONDecodeError) as e:
            return self.error(str(e))
        except Exception as e:
            return self.error(f"{type(e).__name__}: {e}", 500)

    def static(self, path: str):
        if path in ("", "/"):
            path = "/index.html"
        target = (STATIC / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            return self.error("not found", 404)
        ctype = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml"}.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype + "; charset=utf-8",
                   {"Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"})

    def get_api(self, path: str, q: dict):
        L = leads
        if path == "state":
            products = []
            if L.DATA_ROOT.exists():
                products = sorted(p.name for p in L.DATA_ROOT.iterdir() if p.is_dir() and not p.name.startswith("."))
            if L.PRODUCT not in products:
                products.append(L.PRODUCT)
            return self.json({
                "product": L.PRODUCT, "product_name": L.product_name(), "products": products,
                "stages": L.STAGES, "funnel": L.FUNNEL, "columns": L.COLUMNS, "today": L.today(),
                "has_product_md": (L.DATA / "product.md").exists(), "has_icp": (L.DATA / "icp.md").exists(),
                "claude": bool(claude_bin()), "commands": command_info(),
                "running": sum(1 for j in JOBS.values() if j.status == "running"),
            })
        if path == "leads":
            return self.json(L.read_leads())
        if path == "lead":
            row = L.find_lead(L.read_leads(), q.get("id", ""))
            if row is None:
                return self.error("not found", 404)
            out = L.OUTREACH / f"{row['id']}.md"
            return self.json({"lead": row, "notes": L.read_notes(row["id"]),
                              "outreach": out.read_text(encoding="utf-8") if out.exists() else ""})
        if path == "analytics":
            return self.json(L.analytics(L.read_leads()))
        if path == "due":
            b = L.due_buckets(L.read_leads(), int(q.get("days") or 7))
            return self.json(b)
        if path == "dupes":
            return self.json(L.find_dupes(L.read_leads()))
        if path == "views":
            return self.json(L.read_views())
        if path == "templates":
            builtin = L.TEMPLATES_BUILTIN / "outreach"
            return self.json([{"name": n, "text": p.read_text(encoding="utf-8"),
                               "builtin": p.parent == builtin} for n, p in L.list_templates().items()])
        if path == "doc":
            name = q.get("name", "")
            if name not in READABLE_DOCS:
                return self.error("unknown document")
            p = L.DATA / name
            return self.json({"name": name, "text": p.read_text(encoding="utf-8") if p.exists() else "",
                              "editable": name in EDITABLE_DOCS})
        if path == "export":
            rows = L.read_leads()
            ids = set(filter(None, q.get("ids", "").split(",")))
            rows = [r for r in rows if (not ids or r["id"] in ids) and
                    L.matches(r, q=q.get("q", ""), stage=q.get("stage", ""), tag=q.get("tag", ""),
                              min_score=q.get("min_score") or None)]
            fmt = q.get("format", "csv")
            text = L.export_text(rows, fmt)
            name = f"{L.PRODUCT}-leads-{L.today()}{'' if fmt == 'csv' else '-' + fmt}.{L.EXPORT_EXT[fmt]}"
            ctype = {"json": "application/json", "ics": "text/calendar"}.get(fmt, "text/csv")
            return self._send(200, text.encode("utf-8"), ctype + "; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="{name}"'})
        if path == "jobs":
            return self.json([j.summary() for j in sorted(JOBS.values(), key=lambda j: j.started, reverse=True)])
        if path == "job":
            job = JOBS.get(q.get("id", ""))
            if job is None:
                return self.error("not found", 404)
            since = int(q.get("since") or 0)
            return self.json(job.summary() | {"new_lines": job.lines[since:]})
        return self.error("unknown endpoint", 404)

    def post_api(self, path: str, d: dict):
        L = leads
        if path == "product":
            name = L.slugify(str(d.get("name", "")))
            if not name or name == "lead":
                raise ValueError("give the product a name")
            L.DATA_ROOT.mkdir(parents=True, exist_ok=True)
            L.ACTIVE_FILE.write_text(name + "\n", encoding="utf-8")
            (L.DATA_ROOT / name / "notes").mkdir(parents=True, exist_ok=True)
            L.use_product(name)
            return self.json({"product": name})
        if path == "lead/update":
            changes = L.update_lead(d["id"], note=d.get("note", ""), stage=d.get("stage") or None,
                                    next_action=d.get("next_action"), next_date=d.get("next_action_date"),
                                    fields=d.get("fields") or {}, add_tags=d.get("add_tags"),
                                    remove_tags=d.get("remove_tags"))
            return self.json({"changes": changes, "lead": L.find_lead(L.read_leads(), d["id"])})
        if path == "lead/add":
            added, skipped = L.add_leads([d.get("lead") or {}])
            return self.json({"added": [r["id"] for r in added], "skipped": skipped})
        if path == "bulk":
            ids = [str(i) for i in d.get("ids") or []]
            if not ids:
                raise ValueError("select at least one lead")
            done, missing = L.bulk_update(ids, note=d.get("note", ""), stage=d.get("stage") or None,
                                          next_action=d.get("next_action"), next_date=d.get("next_action_date"),
                                          add_tags=d.get("add_tags"), remove_tags=d.get("remove_tags"))
            return self.json({"updated": done, "missing": missing})
        if path == "merge":
            filled = L.merge_leads(d["keep"], d["dup"])
            return self.json({"filled": filled})
        if path == "views":
            name = str(d.get("name", "")).strip()
            if not name:
                raise ValueError("give the view a name")
            return self.json(L.save_view(name, d.get("filters") or {}))
        if path == "views/delete":
            return self.json(L.delete_view(str(d.get("name", ""))))
        if path == "templates":
            name = L.slugify(str(d.get("name", "")))
            if not name or name == "lead":
                raise ValueError("give the template a name")
            L.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            (L.TEMPLATES_DIR / f"{name}.md").write_text(str(d.get("text", "")), encoding="utf-8")
            return self.json({"saved": name})
        if path == "templates/delete":
            name = L.slugify(str(d.get("name", "")))
            p = L.TEMPLATES_DIR / f"{name}.md"
            if not p.exists():
                raise ValueError("only templates saved for this product can be deleted")
            p.unlink()
            return self.json({"deleted": name})
        if path == "render":
            text, missing = L.render_template(d["template"], d["id"])
            return self.json({"text": text, "missing": missing})
        if path == "outreach/save":
            p = L.save_outreach(d["id"], str(d.get("text", "")), str(d.get("label") or "gui"))
            return self.json({"path": str(p.relative_to(L.ROOT))})
        if path == "icp/learn":
            return self.json({"added": L.learn_disqualifier(str(d.get("rule", "")), str(d.get("id", "")))})
        if path == "doc":
            name = d.get("name", "")
            if name not in EDITABLE_DOCS:
                raise ValueError("only product.md and icp.md can be edited")
            L.DATA.mkdir(parents=True, exist_ok=True)
            (L.DATA / name).write_text(str(d.get("text", "")), encoding="utf-8")
            return self.json({"saved": name})
        if path == "import":
            res = L.import_rows(str(d.get("csv", "")).lstrip("﻿"), stage=d.get("stage") or "candidate",
                                source=str(d.get("source", "")).strip(), dry_run=bool(d.get("dry_run")),
                                tags=str(d.get("tags", "")))
            return self.json(res)
        if path == "jobs":
            job = start_job(str(d.get("command", "")), str(d.get("args", "")).replace("\n", " ").strip())
            return self.json(job.summary())
        if path == "job/cancel":
            job = JOBS.get(str(d.get("id", "")))
            if job is None:
                raise KeyError("job")
            if job.proc and job.proc.poll() is None:
                job.status = "cancelled"
                job.proc.terminate()
            return self.json(job.summary())
        return self.error("unknown endpoint", 404)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allowed_host = ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=int(os.environ.get("LEAD_AGENT_PORT", 8765)))
    p.add_argument("--host", default="127.0.0.1",
                   help="address to listen on (default: this computer only; anything else exposes your leads)")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)
    srv = Server((args.host, args.port), Handler)
    srv.allowed_host = args.host
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '') else args.host}:{args.port}"
    print(f"Lead Agent GUI on {url}  (product: {leads.active_product()})  Ctrl+C to stop")
    if not claude_bin():
        print("note: Claude Code CLI not found, so the Run page is disabled. Everything else works.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
