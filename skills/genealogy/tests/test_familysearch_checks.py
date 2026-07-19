"""Unit tests for _familysearch_checks.py's Check D (missing Call Number).

Run with:
    <skill-dir>/scripts/gramps_python -m unittest discover -s <skill-dir>/tests
"""
import json
import os
import subprocess
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(SKILL_DIR, "test-fixtures", "data.gramps")
CHECKS_SCRIPT = os.path.join(SKILL_DIR, "scripts", "_familysearch_checks.py")
GRAMPS_PYTHON = os.path.join(SKILL_DIR, "scripts", "gramps_python")

NO_CALL_NUMBER = "no Call Number"


class FamilySearchCallNumberChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [GRAMPS_PYTHON, CHECKS_SCRIPT, FIXTURE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        cls.stderr = result.stderr
        cls.findings = json.loads(result.stdout)
        cls.call_number_findings = {
            f["record_id"]: f
            for f in cls.findings
            if f["record_type"] == "Source" and NO_CALL_NUMBER in f["message"]
        }

    def test_source_with_call_number_has_no_warning(self):
        # S0000: FamilySearch: Dennis Wayne Varnell, Birth Record — call number set.
        self.assertNotIn(
            "S0000", self.call_number_findings,
            "Source with a Call Number set should not get a missing-call-number warning",
        )

    def test_source_with_very_low_confidence_is_silenced(self):
        # S0001: FamilySearch: Lorraine Decker, Birth Record — no call number, but its
        # only citation is Confidence: Very Low, so the warning should be silenced.
        self.assertNotIn(
            "S0001", self.call_number_findings,
            "Source with no Call Number but all-Very-Low-confidence citations should "
            "have its missing-call-number warning silenced",
        )

    def test_source_with_normal_confidence_still_warns(self):
        # S0002: FamilySearch: Clayton Rufus Varnell, Birth Record — no call number,
        # Normal confidence citation, so the warning should still fire.
        self.assertIn(
            "S0002", self.call_number_findings,
            "Source with no Call Number and non-Very-Low confidence should still warn",
        )
        finding = self.call_number_findings["S0002"]
        self.assertEqual(finding["record_type"], "Source")
        self.assertIn("Clayton Rufus Varnell", finding["record_name"])


if __name__ == "__main__":
    unittest.main()
