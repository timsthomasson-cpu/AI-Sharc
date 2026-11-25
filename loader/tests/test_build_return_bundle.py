"""Tests for loader/build_return_bundle.py (Prompt v1 Shopping Query Returns)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_return_bundle as b  # noqa: E402

NAME = "meta-muse__hvac-houston-77002-t2__r1__20261125T200000-0600__observation.md"
TASK = ("Find all HVAC firms whose service area includes Houston, TX 77002 for AC repair and compare the firms "
        "you find. Rank the firms you find, using Muse ranking.")
MD = "Prompt version: v1\nQuery sent:\n%s\n\nResponse:\n1. Alpha Air ...\n2. Beta Cool ...\n" % TASK


def extract(**over):
    ex = {"prompt_version": "v1", "session_state": "logged in", "web_search_ran": "yes", "ranked": "yes",
          "ranking_origin": "own", "ranking_basis": "reviews and rating", "business_contacted": "no",
          "extracted_by": "Claude test",
          "firms": [{"position": 1, "agent_rank": 1, "name_as_given": "Alpha Air", "phone_as_given": "(713) 555-0101"},
                    {"position": 2, "agent_rank": 2, "name_as_given": "Beta Cool"}]}
    ex.update(over)
    return ex


class BuildReturnBundle(unittest.TestCase):
    def folder(self, md=MD, ex=None, name=NAME):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(md)
        if ex is not None:
            with open(os.path.join(d, name.replace("__observation.md", "__extract.json")), "w") as fh:
                json.dump(ex, fh)
        return d

    def build(self, d):
        return b.main(d, os.path.join(tempfile.mkdtemp(), "out.json"))

    def test_good_run(self):
        out = self.build(self.folder(ex=extract()))
        self.assertEqual(out["problems"], [])
        run = out["runs"][0]["run"]
        self.assertEqual(run["checked_at"], "2026-11-25T20:00:00-06:00")
        self.assertEqual(run["product"], "Muse")
        self.assertEqual(run["town_zip"], "Houston, TX 77002")
        self.assertEqual(run["service_query"], "AC repair")
        self.assertEqual(run["run_id"], NAME[: -len("__observation.md")])
        self.assertEqual(len(out["runs"][0]["file_hash"]), 64)

    def test_waiting_without_extract(self):
        out = self.build(self.folder())
        self.assertEqual(out["waiting_for_extract"], [NAME])
        self.assertEqual(out["runs"], [])

    def test_wrong_wording_rejected(self):
        out = self.build(self.folder(md=MD.replace("Find all HVAC firms", "Find an HVAC firm"), ex=extract()))
        self.assertIn("task text", out["problems"][0]["reason"])

    def test_missing_muse_ranking_line(self):
        out = self.build(self.folder(md=MD.replace(", using Muse ranking", ""), ex=extract()))
        self.assertIn("ranking line", out["problems"][0]["reason"])

    def test_duplicate_rank(self):
        ex = extract()
        ex["firms"][1]["agent_rank"] = 1
        self.assertIn("share an agent_rank", self.build(self.folder(ex=ex))["problems"][0]["reason"])

    def test_positions_in_order(self):
        ex = extract()
        ex["firms"][1]["position"] = 3
        self.assertIn("positions", self.build(self.folder(ex=ex))["problems"][0]["reason"])

    def test_unapproved_prompt_version(self):
        out = self.build(self.folder(ex=extract(prompt_version="v0")))
        self.assertIn("approved version", out["problems"][0]["reason"])

    def test_bad_file_name(self):
        out = self.build(self.folder(ex=extract(), name="MUSE-AGENT — Houston — Task 2__observation.md"))
        self.assertIn("pattern", out["problems"][0]["reason"])

    def test_chatgpt_ranking_line(self):
        name = NAME.replace("meta-muse", "openai-chatgpt")
        md = MD.replace("Rank the firms you find, using Muse ranking.", b.RANK_LINE["default"])
        out = self.build(self.folder(md=md, ex=extract(), name=name))
        self.assertEqual(out["problems"], [])
        self.assertEqual(out["runs"][0]["run"]["vendor"], "OpenAI")

    def test_multiword_town(self):
        self.assertEqual(b.town_zip("hvac-san-antonio-78217-t1"), ("San Antonio", "78217"))


if __name__ == "__main__":
    unittest.main()
