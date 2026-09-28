"""Tests for the modernization extension's overseer gate (`zethus/scripts/overseer-gate.py`):
the constitution-completeness gate, the golden-master-coverage gate, and the higher-environment
credential gate. Fixtures are synthetic — no real constitution, ledger or credential.
"""
from __future__ import annotations

import os
from unittest import mock

from tests.test_zethus import SCRIPTS, TempRepo, load, run

overseer_mod = load(SCRIPTS / "overseer-gate.py")

CONSTITUTION_HEADER = """# Constitution: demo-job

| Field | Value |
|---|---|
| Status | DRAFT |
| Date | 2026-09-28 |
| Owner | someone |
| Rule ledger(s) | rules/demo.json |
| Fixture manifest | fixtures/demo.json |
| HLA reference | docs/hla.md |

"""

ALL_SECTIONS = (
    "Inputs", "Outputs", "Side effects", "Ordering", "Error & restart semantics",
    "Commit / transaction boundaries", "File / message formats", "Exit / status contract",
    "Scheduling / invocation contract",
)


def constitution(sections: dict[str, str]) -> str:
    out = [CONSTITUTION_HEADER]
    for name in ALL_SECTIONS:
        out.append(f"## {name}\n")
        out.append(sections.get(name, "- No rule found — not yet recovered.") + "\n")
    return "\n".join(out)


class ConstitutionGate(TempRepo):
    def gate(self, *argv):
        return run(overseer_mod, "--repo", str(self.repo), "constitution", *argv)

    def test_clear_when_every_section_sourced_or_explicit(self):
        text = constitution({"Inputs": "- [R1] takes a file path — confidence: High"})
        path = self.write("docs/constitution.md", text)
        code, out = self.gate("--constitution", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("clear", out)

    def test_missing_section_is_a_gap(self):
        text = CONSTITUTION_HEADER + "## Inputs\n\n- [R1] x — confidence: High\n"
        path = self.write("docs/constitution.md", text)
        code, out = self.gate("--constitution", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("Outputs", out)
        self.assertIn("gap", out)

    def test_low_confidence_without_waiver_is_a_gap(self):
        text = constitution({"Inputs": "- [R2] guessed from naming — confidence: Low"})
        path = self.write("docs/constitution.md", text)
        code, out = self.gate("--constitution", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("R2", out)
        self.assertIn("waiver", out)

    def test_low_confidence_with_waiver_passes(self):
        text = constitution({"Inputs": "- [R2] guessed from naming — confidence: Low "
                                      "(waiver: 2026-09-28-accept-low-confidence-input)"})
        path = self.write("docs/constitution.md", text)
        code, out = self.gate("--constitution", str(path))
        self.assertEqual(code, 0, out)

    def test_missing_file_is_usage_error(self):
        code, out = self.gate("--constitution", "docs/nope.md")
        self.assertEqual(code, 2)


class GoldenMasterGate(TempRepo):
    def gate(self, *argv):
        return run(overseer_mod, "--repo", str(self.repo), "golden-master", *argv)

    def test_covered_by_legacy_run_fixture_passes(self):
        text = constitution({"Inputs": "- [R1] x — confidence: High"})
        cpath = self.write("docs/constitution.md", text)
        self.write("fixtures/demo.json",
                   '{"fixtures": [{"id": "GM-1", "ruleIds": ["R1"], "source": "legacy-run"}]}')
        code, out = self.gate("--constitution", str(cpath), "--fixtures", "fixtures/demo.json")
        self.assertEqual(code, 0, out)

    def test_uncovered_rule_is_a_gap(self):
        text = constitution({"Inputs": "- [R1] x — confidence: High"})
        cpath = self.write("docs/constitution.md", text)
        self.write("fixtures/demo.json", '{"fixtures": []}')
        code, out = self.gate("--constitution", str(cpath), "--fixtures", "fixtures/demo.json")
        self.assertEqual(code, 1, out)
        self.assertIn("R1", out)

    def test_authored_only_fixture_does_not_count(self):
        text = constitution({"Inputs": "- [R1] x — confidence: High"})
        cpath = self.write("docs/constitution.md", text)
        self.write("fixtures/demo.json",
                   '{"fixtures": [{"id": "GM-1", "ruleIds": ["R1"], "source": "authored"}]}')
        code, out = self.gate("--constitution", str(cpath), "--fixtures", "fixtures/demo.json")
        self.assertEqual(code, 1, out)
        self.assertIn("authored", out)

    def test_fixture_path_read_from_constitution_field(self):
        text = constitution({"Inputs": "- [R1] x — confidence: High"})
        cpath = self.write("docs/constitution.md", text)
        self.write("fixtures/demo.json",
                   '{"fixtures": [{"id": "GM-1", "ruleIds": ["R1"], "source": "legacy-run"}]}')
        code, out = self.gate("--constitution", str(cpath))
        self.assertEqual(code, 0, out)


class CredentialGate(TempRepo):
    def gate(self, *argv):
        return run(overseer_mod, "--repo", str(self.repo), "credential", *argv)

    def test_higher_environment_variable_is_flagged(self):
        self.config({"overseer": {"environments": ["dev", "test", "staging", "prod"],
                                  "currentEnvironment": "dev"}})
        with mock.patch.dict(os.environ, {"PROD_DB_PASSWORD": "s3cret"}):
            code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("PROD_DB_PASSWORD", out)
        self.assertNotIn("s3cret", out)

    def test_same_or_lower_environment_variable_is_not_flagged(self):
        self.config({"overseer": {"environments": ["dev", "test", "staging", "prod"],
                                  "currentEnvironment": "staging"}})
        with mock.patch.dict(os.environ, {"DEV_DB_PASSWORD": "x", "STAGING_DB_PASSWORD": "y"}):
            code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_unrelated_variable_is_ignored(self):
        self.config({"overseer": {"environments": ["dev", "prod"], "currentEnvironment": "dev"}})
        with mock.patch.dict(os.environ, {"PATH_EXTRA_THING": "whatever"}):
            code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_flagged_credential_in_config_file_by_key_name(self):
        self.config({"overseer": {"environments": ["dev", "prod"], "currentEnvironment": "dev",
                                  "credentialCheck": {"configFiles": [".copilot/local.json"]}}})
        self.write(".copilot/local.json", '{"prodApiToken": "abc123"}')
        code, out = self.gate()
        self.assertEqual(code, 1, out)
        self.assertIn("prodApiToken", out)
        self.assertNotIn("abc123", out)

    def test_config_file_value_without_credential_shaped_key_is_ignored(self):
        self.config({"overseer": {"environments": ["dev", "prod"], "currentEnvironment": "dev",
                                  "credentialCheck": {"configFiles": [".copilot/local.json"]}}})
        self.write(".copilot/local.json", '{"prodRegion": "us-east-1"}')
        code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_no_current_environment_is_usage_error(self):
        self.config({"overseer": {"environments": ["dev", "prod"]}})
        code, out = self.gate()
        self.assertEqual(code, 2)

    def test_environment_override_flag(self):
        self.config({"overseer": {"environments": ["dev", "test", "prod"],
                                  "currentEnvironment": "prod"}})
        with mock.patch.dict(os.environ, {"TEST_DB_PASSWORD": "x"}):
            code, out = self.gate("--environment", "dev")
        self.assertEqual(code, 1, out)
