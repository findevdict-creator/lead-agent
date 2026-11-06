"""Tests for scripts/leads.py. Run: python3 -m unittest scripts/test_leads.py"""
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent


class LeadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LEAD_AGENT_ROOT"] = self.tmp.name
        sys.path.insert(0, str(HERE))
        import importlib
        import leads
        importlib.reload(leads)
        self.leads = leads

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("LEAD_AGENT_ROOT", None)

    def run_cmd(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.leads.main(list(argv))
        return code, buf.getvalue()

    def sample(self, **over):
        d = {
            "company": "Acme Corp", "website": "https://www.acme.com/",
            "industry": "Logistics", "fit_score": 82,
            "fit_reason": "hiring SDRs", "signals": ["hiring", "seed"],
            "sources": ["https://acme.com/about", "https://news.example/acme"],
        }
        d.update(over)
        return json.dumps(d)

    def test_add_and_dedupe(self):
        code, out = self.run_cmd("add", self.sample())
        self.assertEqual(code, 0)
        self.assertIn("added    acme-corp", out)
        # same domain, different name and scheme -> skipped
        code, out = self.run_cmd("add", self.sample(company="ACME Inc", website="http://acme.com"))
        self.assertIn("duplicate domain acme.com", out)
        # same id -> skipped
        code, out = self.run_cmd("add", self.sample(website="https://other.com"))
        self.assertIn("duplicate id", out)
        # no sources -> skipped
        code, out = self.run_cmd("add", self.sample(company="Nosrc", website="https://nosrc.com", sources=[]))
        self.assertIn("no sources", out)
        rows = self.leads.read_leads()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signals"], "hiring; seed")
        self.assertEqual(rows[0]["stage"], "new")

    def test_add_many_from_file(self):
        path = Path(self.tmp.name) / "batch.json"
        path.write_text(json.dumps([
            json.loads(self.sample()),
            json.loads(self.sample(company="Beta", website="beta.io", fit_score=55)),
        ]))
        code, out = self.run_cmd("add", "--file", str(path))
        self.assertIn("2 added", out)

    def test_update_and_notes(self):
        self.run_cmd("add", self.sample())
        code, out = self.run_cmd("update", "acme-corp", "--stage", "approved",
                                 "--note", "looks great", "--next-date", "2030-01-01")
        self.assertEqual(code, 0)
        row = self.leads.read_leads()[0]
        self.assertEqual(row["stage"], "approved")
        self.assertEqual(row["next_action_date"], "2030-01-01")
        note = (Path(self.tmp.name) / "data" / "notes" / "acme-corp.md").read_text()
        self.assertIn("looks great", note)
        code, _ = self.run_cmd("update", "acme-corp", "--stage", "bogus")
        self.assertEqual(code, 1)
        code, _ = self.run_cmd("update", "missing", "--stage", "won")
        self.assertEqual(code, 1)

    def test_list_stats_export(self):
        self.run_cmd("add", self.sample())
        self.run_cmd("add", self.sample(company="Beta", website="beta.io", fit_score=55))
        code, out = self.run_cmd("list", "--limit", "1")
        self.assertIn("acme-corp", out)
        self.assertNotIn("beta", out)
        self.run_cmd("update", "beta", "--stage", "approved", "--next-date", "2000-01-01",
                     "--next-action", "call")
        code, out = self.run_cmd("stats")
        self.assertIn("total leads: 2", out)
        self.assertIn("overdue", out)
        self.assertIn("top approved", out)
        out_path = Path(self.tmp.name) / "x.csv"
        code, out = self.run_cmd("export", "--stage", "approved", "--out", str(out_path))
        with out_path.open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["id"] for r in rows], ["beta"])

    def test_search_log(self):
        self.run_cmd("log-search", "logistics startups berlin", "--found", "3")
        code, out = self.run_cmd("searches")
        self.assertIn("logistics startups berlin", out)

    def test_normalize_domain(self):
        n = self.leads.normalize_domain
        self.assertEqual(n("https://www.Acme.com/x?y=1"), "acme.com")
        self.assertEqual(n("acme.com"), "acme.com")
        self.assertEqual(n(""), "")


if __name__ == "__main__":
    unittest.main()
