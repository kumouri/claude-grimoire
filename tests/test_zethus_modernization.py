"""Contract tests for the modernization extension's own kit pieces: the five new skills'
frontmatter, that recover-business-rules links every per-shape reader it composes with, and that
the constitution template's sections match what `_ledger.py` requires the overseer gates to parse.
"""
from __future__ import annotations

import json
import unittest

from tests.test_zethus import KIT, frontmatter, load

ledger_mod = load(KIT / "scripts" / "_ledger.py")

MODERNIZATION_SKILLS = {
    "recover-business-rules", "batch-type-spring-jpa-jdbc", "batch-type-ksh-scripts",
    "batch-type-cron-scheduler-wrappers", "dialect-oracle-plsql",
}


def headings(path):
    return [ln[3:].strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.startswith("## ")]


class ModernizationSkills(unittest.TestCase):
    def test_every_modernization_skill_exists_with_valid_frontmatter(self):
        for name in MODERNIZATION_SKILLS:
            path = KIT / "skills" / name / "SKILL.md"
            self.assertTrue(path.is_file(), name)
            fm = frontmatter(path)
            self.assertEqual(fm.get("name"), name, f"{name}: name must match its directory")
            self.assertRegex(fm["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
            self.assertLessEqual(len(fm["name"]), 64)
            self.assertTrue(fm.get("description"), f"{name}: description is required")
            self.assertLessEqual(len(fm["description"]), 1024, name)

    def test_recover_business_rules_links_every_reader(self):
        text = (KIT / "skills/recover-business-rules/SKILL.md").read_text(encoding="utf-8")
        for name in MODERNIZATION_SKILLS - {"recover-business-rules"}:
            self.assertIn(f"../{name}/SKILL.md", text, name)

    def test_every_reader_links_back_to_recover_business_rules(self):
        for name in MODERNIZATION_SKILLS - {"recover-business-rules"}:
            text = (KIT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("../recover-business-rules/SKILL.md", text, name)

    def test_dialect_oracle_plsql_uses_the_hla_and_intake_scripts(self):
        text = (KIT / "skills/dialect-oracle-plsql/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/hla-input-check.py", text)
        self.assertIn("scripts/plsql-ddl-intake.py", text)


class ConstitutionTemplate(unittest.TestCase):
    def test_headings_match_the_ledger_modules_required_sections(self):
        found = headings(KIT / "templates/constitution.md")
        self.assertEqual(found, list(ledger_mod.REQUIRED_SECTIONS))

    def test_field_table_has_the_fields_the_overseer_reads(self):
        text = (KIT / "templates/constitution.md").read_text(encoding="utf-8")
        for field in ("Rule ledger(s)", "Fixture manifest"):
            self.assertIn(f"| {field} |", text)

    def test_example_fixture_manifest_has_a_legacy_run_source(self):
        data = json.loads((KIT / "templates/fixture-manifest.example.json").read_text(encoding="utf-8"))
        self.assertTrue(data["fixtures"])
        self.assertEqual(data["fixtures"][0]["source"], "legacy-run")
