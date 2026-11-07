"""Smoke tests for scripts/gui.py. Run: python3 -m unittest scripts/test_gui.py"""
import http.client
import importlib
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class GuiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LEAD_AGENT_ROOT"] = self.tmp.name
        sys.path.insert(0, str(HERE))
        import leads
        import gui
        importlib.reload(leads)
        self.gui = importlib.reload(gui)
        self.leads = self.gui.leads
        self.leads.add_leads([{"company": "Acme", "website": "acme.com", "fit_score": 80,
                               "sources": ["https://acme.com"], "signals": ["hiring"]}])
        self.srv = self.gui.Server(("127.0.0.1", 0), self.gui.Handler)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()
        os.environ.pop("LEAD_AGENT_ROOT", None)
        os.environ.pop("LEAD_AGENT_CLAUDE", None)

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Content-Type": "application/json", "X-Lead-Agent": "1"}
        h.update(headers or {})
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, data

    def test_read_and_update(self):
        code, data = self.req("GET", "/api/leads")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)[0]["id"], "acme")
        code, data = self.req("POST", "/api/lead/update", {"id": "acme", "stage": "approved", "add_tags": ["DACH"]})
        self.assertEqual(code, 200, data)
        row = self.leads.read_leads()[0]
        self.assertEqual((row["stage"], row["tags"]), ("approved", "dach"))
        code, _ = self.req("POST", "/api/lead/update", {"id": "missing", "stage": "won"})
        self.assertEqual(code, 404)
        code, _ = self.req("POST", "/api/lead/update", {"id": "acme", "stage": "bogus"})
        self.assertEqual(code, 400)

    def test_guards(self):
        code, _ = self.req("POST", "/api/bulk", {"ids": ["acme"], "stage": "won"}, {"X-Lead-Agent": ""})
        self.assertEqual(code, 403)
        code, _ = self.req("GET", "/api/leads", headers={"Host": "evil.example"})
        self.assertEqual(code, 403)
        code, _ = self.req("GET", "/../scripts/leads.py")
        self.assertEqual(code, 404)
        code, data = self.req("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b"Lead Agent", data)
        code, _ = self.req("POST", "/api/doc", {"name": "../../etc/passwd", "text": "x"})
        self.assertEqual(code, 400)

    def test_export_and_analytics(self):
        code, data = self.req("GET", "/api/export?format=hubspot")
        self.assertEqual(code, 200)
        self.assertIn(b"Company Domain Name", data)
        code, data = self.req("GET", "/api/analytics")
        self.assertEqual(json.loads(data)["total"], 1)

    def test_run_job_with_fake_claude(self):
        fake = Path(self.tmp.name) / "fakeclaude"
        fake.write_text("#!/bin/sh\n"
                        "echo '{\"type\":\"assistant\",\"message\":{\"content\":[{\"type\":\"tool_use\",\"name\":\"WebSearch\",\"input\":{\"query\":\"q\"}}]}}'\n"
                        "echo \"{\\\"type\\\":\\\"result\\\",\\\"result\\\":\\\"got $2 for $LEAD_AGENT_PRODUCT\\\"}\"\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        os.environ["LEAD_AGENT_CLAUDE"] = str(fake)
        code, _ = self.req("POST", "/api/jobs", {"command": "rm -rf", "args": ""})
        self.assertEqual(code, 400)
        code, data = self.req("POST", "/api/jobs", {"command": "find-leads", "args": "5"})
        self.assertEqual(code, 200, data)
        job_id = json.loads(data)["id"]
        for _ in range(50):
            job = json.loads(self.req("GET", f"/api/job?id={job_id}")[1])
            if job["status"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(job["status"], "done")
        self.assertIn("→ WebSearch: q", job["new_lines"])
        self.assertIn("got /find-leads 5 for default", job["new_lines"])


if __name__ == "__main__":
    unittest.main()
