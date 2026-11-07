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

    def test_same_domain_different_people_kept(self):
        self.run_cmd("add", self.sample(contact_name="Ann Lee"))
        code, out = self.run_cmd("add", self.sample(company="Acme Corp Coach Bob", contact_name="Bob Ray"))
        self.assertIn("added", out)
        code, out = self.run_cmd("add", self.sample(company="Acme Corp Again", contact_name="Ann Lee"))
        self.assertIn("duplicate domain", out)
        code, out = self.run_cmd("add", self.sample(company="Acme Corp Nobody"))
        self.assertIn("duplicate domain", out)

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
        note = (Path(self.tmp.name) / "data" / "default" / "notes" / "acme-corp.md").read_text()
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

    def test_digest(self):
        self.run_cmd("add", self.sample())
        self.run_cmd("add", self.sample(company="Beta", website="beta.io", fit_score=55))
        self.run_cmd("update", "beta", "--stage", "contacted", "--next-action", "ping",
                     "--next-date", "2000-01-01")
        code, out = self.run_cmd("digest", "--days", "3")
        self.assertEqual(code, 0)
        self.assertIn("added: 2", out)
        self.assertIn("overdue: 1", out)
        self.assertIn("funnel: candidate 0 → new 1 → approved 0 → contacted 1", out)

    def test_products(self):
        self.run_cmd("add", self.sample())
        self.assertTrue((Path(self.tmp.name) / "data" / "default" / "leads.csv").exists())
        code, out = self.run_cmd("product", "Watt Wisely")
        self.assertIn("active product: watt-wisely", out)
        import importlib
        leads = importlib.reload(self.leads)
        self.leads = leads
        self.assertEqual(leads.PRODUCT, "watt-wisely")
        code, out = self.run_cmd("list")
        self.assertIn("no leads", out)
        code, out = self.run_cmd("products")
        self.assertIn("* watt-wisely", out)
        self.assertIn("  default", out)
        self.assertIn("leads=1", out)

    def test_search_log(self):
        self.run_cmd("log-search", "logistics startups berlin", "--found", "3")
        code, out = self.run_cmd("searches")
        self.assertIn("logistics startups berlin", out)

    def test_slugify(self):
        s = self.leads.slugify
        self.assertEqual(s("Stadtwerke Lübeck"), "stadtwerke-luebeck")
        self.assertEqual(s("Café Münster GmbH"), "cafe-muenster-gmbh")
        self.assertEqual(s("  Acme, Inc. "), "acme-inc")

    def test_normalize_domain(self):
        n = self.leads.normalize_domain
        self.assertEqual(n("https://www.Acme.com/x?y=1"), "acme.com")
        self.assertEqual(n("acme.com"), "acme.com")
        self.assertEqual(n(""), "")

    def test_filters_tags_and_bulk(self):
        self.run_cmd("add", self.sample(tags=["DACH", "warm"]))
        self.run_cmd("add", self.sample(company="Beta", website="beta.io", fit_score=55))
        code, out = self.run_cmd("list", "--tag", "dach")
        self.assertIn("acme-corp", out)
        self.assertNotIn("beta", out)
        code, out = self.run_cmd("list", "--min-score", "60")
        self.assertNotIn("beta", out)
        code, out = self.run_cmd("list", "--q", "acme hiring")
        self.assertIn("acme-corp", out)
        code, out = self.run_cmd("bulk-update", "acme-corp", "beta", "--stage", "approved",
                                 "--add-tag", "Q4 push", "--note", "batch")
        self.assertEqual(code, 0)
        rows = {r["id"]: r for r in self.leads.read_leads()}
        self.assertEqual(rows["beta"]["stage"], "approved")
        self.assertEqual(rows["acme-corp"]["tags"], "dach; warm; q4-push")
        code, _ = self.run_cmd("tag", "beta", "q4-push", "--remove")
        self.assertEqual(self.leads.read_leads()[1]["tags"], "")
        code, _ = self.run_cmd("bulk-update", "beta", "nope", "--stage", "won")
        self.assertEqual(code, 1)
        code, _ = self.run_cmd("bulk-update", "beta", "--stage", "bogus")
        self.assertEqual(code, 1)

    def test_old_csv_without_tags_column(self):
        data = Path(self.tmp.name) / "data" / "default"
        data.mkdir(parents=True)
        cols = [c for c in self.leads.COLUMNS if c != "tags"]
        with (data / "leads.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerow({c: "" for c in cols} | {"id": "old", "company": "Old", "stage": "new"})
        self.run_cmd("tag", "old", "legacy")
        with (data / "leads.csv").open() as f:
            row = next(csv.DictReader(f))
        self.assertEqual(row["tags"], "legacy")

    def test_due_and_ics(self):
        self.run_cmd("add", self.sample())
        self.run_cmd("add", self.sample(company="Beta", website="beta.io"))
        self.run_cmd("add", self.sample(company="Gamma", website="gamma.io"))
        self.run_cmd("update", "acme-corp", "--stage", "contacted", "--next-date", "2000-01-01",
                     "--next-action", "Call, then email")
        self.run_cmd("update", "beta", "--stage", "approved")
        code, out = self.run_cmd("due")
        self.assertIn("overdue: 1", out)
        self.assertIn("no next action date: 1", out)
        ics = self.leads.calendar_ics(self.leads.read_leads())
        self.assertIn("DTSTART;VALUE=DATE:20000101", ics)
        self.assertIn("SUMMARY:Call\\, then email: Acme Corp", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 1)

    def test_export_formats(self):
        self.run_cmd("add", self.sample(contact_name="Jane Q Doe", contact_email="jane@acme.com"))
        for fmt in ("hubspot", "pipedrive", "json", "ics", "csv"):
            out_path = Path(self.tmp.name) / f"x.{fmt}"
            code, _ = self.run_cmd("export", "--format", fmt, "--out", str(out_path))
            self.assertEqual(code, 0)
            self.assertTrue(out_path.read_text())
        with (Path(self.tmp.name) / "x.hubspot").open() as f:
            row = next(csv.DictReader(f))
        self.assertEqual((row["First Name"], row["Last Name"], row["Company Domain Name"]),
                         ("Jane", "Q Doe", "acme.com"))
        self.assertEqual(json.loads((Path(self.tmp.name) / "x.json").read_text())[0]["id"], "acme-corp")

    def test_analytics(self):
        self.run_cmd("add", self.sample())
        self.run_cmd("add", self.sample(company="Beta", website="beta.io", stage="candidate", fit_score=30))
        self.run_cmd("add", self.sample(company="Gamma", website="gamma.io"))
        self.run_cmd("update", "acme-corp", "--stage", "replied")
        self.run_cmd("update", "gamma", "--stage", "lost")
        a = self.leads.analytics(self.leads.read_leads())
        funnel = {f["stage"]: f["count"] for f in a["funnel"]}
        self.assertEqual(funnel["candidate"], 3)
        self.assertEqual(funnel["new"], 2)
        self.assertEqual(funnel["contacted"], 2)
        self.assertEqual(funnel["replied"], 1)
        self.assertEqual(a["reply_rate"], 50)
        self.assertEqual(a["win_rate"], 0)
        self.assertIn(("acme.com", 3), a["top_sources"])
        code, out = self.run_cmd("analytics")
        self.assertIn("reply rate: 50%", out)

    def test_import(self):
        path = Path(self.tmp.name) / "in.csv"
        path.write_text("Company Name,Website,Email,Job Title,Source\n"
                        "Delta GmbH,delta.de,info@delta.de,CEO,https://list.example/x\n"
                        "Acme,acme.com,,,\n"
                        "Echo,echo.io,,,\n", encoding="utf-8")
        code, out = self.run_cmd("import", str(path), "--dry-run")
        self.assertIn("3 rows would be imported", out)
        self.assertEqual(self.leads.read_leads(), [])
        code, out = self.run_cmd("import", str(path))
        self.assertIn("1 added, 2 skipped", out)
        self.run_cmd("add", self.sample())
        code, out = self.run_cmd("import", str(path), "--source", "my-crm-export", "--tag", "crm")
        self.assertIn("1 added, 2 skipped", out)
        rows = {r["id"]: r for r in self.leads.read_leads()}
        self.assertEqual(rows["delta-gmbh"]["stage"], "candidate")
        self.assertEqual(rows["delta-gmbh"]["contact_email"], "info@delta.de")
        self.assertEqual(rows["echo"]["tags"], "crm")

    def test_dupes_and_merge(self):
        self.run_cmd("add", self.sample(contact_email="a@acme.com", sources=["https://a.example"]))
        self.run_cmd("add", self.sample(company="ACME Corp GmbH", website="https://acme.de",
                                        industry="", location="Berlin", fit_score=90,
                                        sources=["https://b.example"]))
        code, out = self.run_cmd("dupes")
        self.assertIn("acme-corp, acme-corp-gmbh", out)
        code, out = self.run_cmd("merge", "acme-corp", "acme-corp-gmbh")
        self.assertEqual(code, 0)
        rows = {r["id"]: r for r in self.leads.read_leads()}
        self.assertEqual(rows["acme-corp"]["location"], "Berlin")
        self.assertEqual(rows["acme-corp"]["fit_score"], "90")
        self.assertIn("https://b.example", rows["acme-corp"]["sources"])
        self.assertEqual(rows["acme-corp-gmbh"]["stage"], "rejected")
        code, out = self.run_cmd("dupes")
        self.assertIn("no likely duplicates", out)

    def test_templates_render(self):
        tdir = Path(self.tmp.name) / "templates" / "outreach"
        tdir.mkdir(parents=True)
        (tdir / "hello.md").write_text("{{greeting}} about {{hook}} at {{company}} for {{contact_role}}")
        self.run_cmd("add", self.sample(contact_name="Jane Doe"))
        text, missing = self.leads.render_template("hello", "acme-corp")
        self.assertEqual(text, "Hi Jane, about hiring at Acme Corp for [contact_role]")
        self.assertEqual(missing, ["contact_role"])
        code, out = self.run_cmd("render", "hello", "acme-corp", "--save")
        self.assertEqual(code, 0)
        draft = (Path(self.tmp.name) / "outreach" / "default" / "acme-corp.md").read_text()
        self.assertIn("not sent", draft)
        row = self.leads.read_leads()[0]
        self.assertEqual(row["next_action"], "Send first message")
        self.assertEqual(row["stage"], "new")

    def test_views(self):
        self.leads.save_view("hot", {"stage": "new", "min_score": 70})
        self.leads.save_view("hot", {"stage": "approved"})
        self.assertEqual(self.leads.read_views(), [{"name": "hot", "filters": {"stage": "approved"}}])
        self.leads.delete_view("hot")
        self.assertEqual(self.leads.read_views(), [])

    def test_learn_disqualifier(self):
        icp = Path(self.tmp.name) / "data" / "default" / "icp.md"
        icp.parent.mkdir(parents=True)
        icp.write_text("# ICP\n\n## Learned disqualifiers\n\n- agencies (from x, 2026-01-01)\n\n## Queries\n- q\n")
        self.assertTrue(self.leads.learn_disqualifier("Too big: 5000+ staff", "acme"))
        self.assertFalse(self.leads.learn_disqualifier("too big: 5000+ staff"))
        text = icp.read_text()
        self.assertIn("- agencies (from x, 2026-01-01)\n- Too big: 5000+ staff (from acme,", text)
        self.assertTrue(text.rstrip().endswith("- q"))

    def test_builtin_templates_render(self):
        import shutil
        shutil.copytree(HERE.parent / "templates", Path(self.tmp.name) / "templates")
        self.run_cmd("add", self.sample())
        for name in self.leads.list_templates():
            text, _ = self.leads.render_template(name, "acme-corp")
            self.assertNotIn("{{", text)


if __name__ == "__main__":
    unittest.main()
