"""Contract and golden-fixture tests for the Jira integration extension: the two new skills'
frontmatter and cross-links, the Jira-access detection script (mocked, no network), and the
structure of the worked example fixtures each skill ships (spec -> stories, story -> enrichment).

See zethus/docs/jira-skills.md for what "decent" means and the approval guardrail these skills
implement; this file checks the shape the doc promises, not prose quality.
"""
from __future__ import annotations

import json
import os
import re
import unittest
from unittest import mock

from tests.test_zethus import KIT, frontmatter, headings, load, run

jira_access_mod = load(KIT / "scripts" / "jira-access.py")

JIRA_SKILLS = {"spec-to-stories", "story-enrich"}

SPEC_TO_STORIES_EXAMPLE = KIT / "skills" / "spec-to-stories" / "example"
STORY_ENRICH_EXAMPLE = KIT / "skills" / "story-enrich" / "example"

STORY_REQUIRED_HEADINGS = {
    "User story", "Context", "Acceptance criteria", "Out of scope", "Dependencies",
    "INVEST self-check",
}
INVEST_CRITERIA = ("Independent", "Negotiable", "Valuable", "Estimable", "Small", "Testable")

ENRICHED_REQUIRED_HEADINGS = {
    "Summary", "What it actually touches", "Current behaviour", "Acceptance criteria",
    "Risks & edge cases", "Open questions for the PO", "Evidence", "Links",
}

FORBIDDEN_SNIPPETS = ("Traceback (most recent call last)", "```")


class JiraSkillsContract(unittest.TestCase):
    def test_every_jira_skill_exists_with_valid_frontmatter(self):
        for name in JIRA_SKILLS:
            path = KIT / "skills" / name / "SKILL.md"
            self.assertTrue(path.is_file(), name)
            fm = frontmatter(path)
            self.assertEqual(fm.get("name"), name, f"{name}: name must match its directory")
            self.assertRegex(fm["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
            self.assertLessEqual(len(fm["name"]), 64)
            self.assertTrue(fm.get("description"), f"{name}: description is required")
            self.assertLessEqual(len(fm["description"]), 1024, name)

    def test_spec_to_stories_links_story_enrich_and_back(self):
        forward = (KIT / "skills/spec-to-stories/SKILL.md").read_text(encoding="utf-8")
        back = (KIT / "skills/story-enrich/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("../story-enrich/SKILL.md", forward)
        self.assertIn("../spec-to-stories/SKILL.md", back)

    def test_both_skills_reference_the_shared_research_and_pr_skills(self):
        text = (KIT / "skills/story-enrich/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("../research-existing-code/SKILL.md", text)

    def test_both_skills_state_the_draft_only_guardrail(self):
        for name in JIRA_SKILLS:
            text = (KIT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Guardrail", text)
            self.assertIn("approval", text.lower())

    def test_jira_doc_defines_decent_and_the_guardrail(self):
        text = (KIT / "docs/jira-skills.md").read_text(encoding="utf-8")
        found = headings(KIT / "docs/jira-skills.md")
        self.assertIn("What \"decent\" means", found)
        self.assertIn("The approval guardrail", found)
        self.assertIn("INVEST", text)

    def test_readme_lists_both_skills_and_new_config_keys(self):
        readme = (KIT / "README.md").read_text(encoding="utf-8")
        for name in JIRA_SKILLS:
            self.assertIn(f"skills/{name}", readme)
        for key in ("stories.dir", "jira.cli", "jira.baseUrlEnv", "jira.emailEnv",
                    "jira.tokenEnvVars"):
            self.assertIn(key, readme)

    def test_example_config_has_the_new_optional_keys(self):
        config = json.loads((KIT / "zethus.config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(config["stories"]["dir"], "docs/stories")
        self.assertEqual(config["jira"]["cli"], ["acli", "jira"])
        self.assertEqual(config["jira"]["baseUrlEnv"], "JIRA_BASE_URL")
        self.assertEqual(config["jira"]["emailEnv"], "JIRA_EMAIL")
        self.assertEqual(config["jira"]["tokenEnvVars"], ["JIRA_API_TOKEN", "JIRA_TOKEN"])


class JiraAccessDetection(unittest.TestCase):
    """No network, no subprocess: ``detect`` takes its environment and its ``which`` as plain
    arguments, so a fake dict and a fake function are the mocks — no ``unittest.mock`` needed for
    the detection logic itself, only for exercising ``main()``'s real ``os.environ``/``shutil``."""

    def which_only(self, *names: str):
        return lambda name: ("/usr/bin/" + name) if name in names else None

    def test_cli_found_wins_immediately(self):
        result = jira_access_mod.detect({}, {}, which=self.which_only("acli"))
        self.assertEqual(result, {"mode": "cli", "detail": "acli"})

    def test_cli_checks_candidates_in_order(self):
        result = jira_access_mod.detect({}, {}, which=self.which_only("jira"))
        self.assertEqual(result["detail"], "jira")

    def test_rest_needs_all_three_fields(self):
        env = {"JIRA_BASE_URL": "https://example.atlassian.net", "JIRA_EMAIL": "a@example.com"}
        result = jira_access_mod.detect({}, env, which=self.which_only())
        self.assertEqual(result["mode"], "none", "missing token: not enough for REST")

    def test_rest_detected_with_all_three_fields(self):
        env = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_EMAIL": "a@example.com",
            "JIRA_API_TOKEN": "secret-value",
        }
        result = jira_access_mod.detect({}, env, which=self.which_only())
        self.assertEqual(result["mode"], "rest")
        self.assertEqual(result["detail"]["tokenVar"], "JIRA_API_TOKEN")
        self.assertNotIn("secret-value", json.dumps(result), "the token value itself must never "
                          "appear in the result, only which env var held it")

    def test_cli_wins_over_rest_when_both_available(self):
        env = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_EMAIL": "a@example.com",
            "JIRA_TOKEN": "secret-value",
        }
        result = jira_access_mod.detect({}, env, which=self.which_only("acli"))
        self.assertEqual(result["mode"], "cli")

    def test_none_detected_when_nothing_is_available(self):
        result = jira_access_mod.detect({}, {}, which=self.which_only())
        self.assertEqual(result, {"mode": "none", "detail": None})

    def test_config_overrides_cli_candidates_and_env_var_names(self):
        config = {"jira": {"cli": ["my-jira-cli"], "baseUrlEnv": "MY_BASE",
                            "emailEnv": "MY_EMAIL", "tokenEnvVars": ["MY_TOKEN"]}}
        default_named_env = {"JIRA_BASE_URL": "https://default.atlassian.net",
                              "JIRA_EMAIL": "default@example.com", "JIRA_API_TOKEN": "t"}
        self.assertEqual(
            jira_access_mod.detect(config, default_named_env, which=self.which_only())["mode"],
            "none", "default-named env vars must be ignored once config overrides the names",
        )
        custom_named_env = {"MY_BASE": "https://example.atlassian.net", "MY_EMAIL": "a@example.com",
                             "MY_TOKEN": "t"}
        self.assertEqual(
            jira_access_mod.detect(config, custom_named_env, which=self.which_only())["mode"],
            "rest",
        )
        self.assertEqual(
            jira_access_mod.detect({}, {}, which=self.which_only("my-jira-cli"))["mode"], "none",
            "an unconfigured custom CLI name must not be found by default",
        )
        self.assertEqual(
            jira_access_mod.detect(config, {}, which=self.which_only("my-jira-cli"))["mode"],
            "cli",
        )

    def test_main_exits_1_and_says_none_when_nothing_is_on_path_or_in_env(self):
        # Force a CLI name that cannot exist, so this is deterministic regardless of the host's
        # real PATH or a developer's own JIRA_* environment variables.
        config = {"jira": {"cli": ["definitely-not-a-real-jira-cli-xyz"],
                            "baseUrlEnv": "T_BASE", "emailEnv": "T_EMAIL",
                            "tokenEnvVars": ["T_TOK"]}}
        with mock.patch.dict(os.environ, {}, clear=True):
            code, out = run(jira_access_mod, "--repo", str(KIT.parent),
                             "--config", str(_write_tmp_config(self, config)))
        self.assertEqual(code, 1)
        self.assertIn("none", out)

    def test_main_reports_cli_mode_and_never_prints_a_token(self):
        config = {"jira": {"cli": ["fake-cli"]}}
        with mock.patch("shutil.which", return_value="/usr/bin/fake-cli"):
            code, out = run(jira_access_mod, "--repo", str(KIT.parent),
                             "--config", str(_write_tmp_config(self, config)))
        self.assertEqual(code, 0)
        self.assertIn("cli:", out)

    def test_main_reports_rest_mode_without_printing_the_token_value(self):
        config = {"jira": {"cli": ["definitely-not-a-real-jira-cli-xyz"]}}
        env = {"JIRA_BASE_URL": "https://example.atlassian.net", "JIRA_EMAIL": "a@example.com",
               "JIRA_API_TOKEN": "super-secret-value"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("shutil.which", return_value=None):
            code, out = run(jira_access_mod, "--repo", str(KIT.parent),
                             "--config", str(_write_tmp_config(self, config)))
        self.assertEqual(code, 0)
        self.assertIn("rest:", out)
        self.assertNotIn("super-secret-value", out)


def _write_tmp_config(test: unittest.TestCase, data: dict):
    import tempfile
    from pathlib import Path
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    path = Path(tmp.name) / "jira.config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class SpecToStoriesExample(unittest.TestCase):
    """Golden structure test: a synthetic two-phase spec, and the stories+index it should produce.
    Checks shape (headings, the INVEST table, epic grouping, the flag mechanism) — not prose, which
    is the agent's judgment call and isn't scriptable."""

    def story_files(self):
        return sorted(SPEC_TO_STORIES_EXAMPLE.glob("[0-9][0-9][0-9][0-9]-*.md"))

    def test_example_directory_exists_with_spec_index_and_stories(self):
        self.assertTrue((SPEC_TO_STORIES_EXAMPLE / "spec.md").is_file())
        self.assertTrue((SPEC_TO_STORIES_EXAMPLE / "index.md").is_file())
        self.assertGreaterEqual(len(self.story_files()), 2, "at least one story per phase")

    def test_index_groups_stories_under_epic_headings_because_the_spec_has_phases(self):
        found = headings(SPEC_TO_STORIES_EXAMPLE / "index.md")
        self.assertGreaterEqual(len(found), 2, "one heading per phase in the example spec")
        index_text = (SPEC_TO_STORIES_EXAMPLE / "index.md").read_text(encoding="utf-8")
        for path in self.story_files():
            self.assertIn(path.name, index_text, f"{path.name} must be linked from the index")

    def test_every_story_has_the_required_sections_and_a_complete_invest_table(self):
        for path in self.story_files():
            found = headings(path)
            missing = STORY_REQUIRED_HEADINGS - set(found)
            self.assertFalse(missing, f"{path.name} missing headings: {missing}")
            text = path.read_text(encoding="utf-8")
            for criterion in INVEST_CRITERIA:
                self.assertIn(f"| {criterion} |", text, f"{path.name}: missing {criterion} row")
            self.assertIn("**Flagged:**", text, f"{path.name}: must state its flag status")

    def test_at_least_one_story_is_flagged_and_explains_why(self):
        flagged = []
        for path in self.story_files():
            text = path.read_text(encoding="utf-8")
            line = next(ln for ln in text.splitlines() if ln.startswith("**Flagged:**"))
            if "none" not in line.lower():
                flagged.append((path, line))
        self.assertTrue(flagged, "the worked example should demonstrate the flag mechanism")
        for path, line in flagged:
            self.assertGreater(len(line), len("**Flagged:**"), f"{path.name}: flag has no reason")

    def test_flagged_story_names_its_dependency_instead_of_hiding_it(self):
        for path in self.story_files():
            text = path.read_text(encoding="utf-8")
            if "**Flagged:**" in text and "none" not in text.split("**Flagged:**")[1].lower()[:20]:
                self.assertNotIn("None known", text, f"{path.name}: a flagged dependency must be "
                                  "named in Dependencies, not left as 'None known'")

    def test_no_story_invents_a_story_point(self):
        for path in self.story_files():
            text = path.read_text(encoding="utf-8").lower()
            for token in ("story point", "3 points", "5 points", "8 points", "t-shirt size"):
                self.assertNotIn(token, text, f"{path.name}: sizing must never be invented")


class StoryEnrichExample(unittest.TestCase):
    """Golden structure test: a synthetic pasted-in story, and its enrichment plus diff."""

    def test_example_files_exist(self):
        for name in ("story-before.md", "story-enriched.md", "story-enriched.diff"):
            self.assertTrue((STORY_ENRICH_EXAMPLE / name).is_file(), name)

    def test_enriched_story_has_every_required_section(self):
        found = set(headings(STORY_ENRICH_EXAMPLE / "story-enriched.md"))
        missing = ENRICHED_REQUIRED_HEADINGS - found
        self.assertFalse(missing, f"missing headings: {missing}")

    def test_enriched_story_cites_file_and_line(self):
        text = (STORY_ENRICH_EXAMPLE / "story-enriched.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"[\w./]+\.py:\d+", "at least one file:line citation is expected")

    def test_enriched_story_is_human_relevant_only(self):
        text = (STORY_ENRICH_EXAMPLE / "story-enriched.md").read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            self.assertNotIn(snippet, text, f"must not contain: {snippet!r}")

    def test_acceptance_criteria_numbers_are_cited_or_flagged_as_proposals(self):
        """Every concrete number in an acceptance-criteria bullet must either come with a
        ``file:line`` citation or be marked ``(proposed: ...)`` for the PO. A bare invented number
        stated as fact is exactly the confidently-wrong failure story-enrich exists to prevent."""
        text = (STORY_ENRICH_EXAMPLE / "story-enriched.md").read_text(encoding="utf-8")
        section = text.split("## Acceptance criteria", 1)[1].split("\n## ", 1)[0]
        items = [item for item in re.split(r"\n(?=- \[)", section.strip()) if item.strip()]
        self.assertTrue(items, "expected at least one acceptance-criteria bullet")
        number_re = re.compile(r"(?<![\w.:/-])\d+(?![\w])")
        citation_re = re.compile(r"[\w./]+\.\w+:\d+")
        for item in items:
            numbers = number_re.findall(item)
            if not numbers:
                continue
            self.assertTrue(
                "(proposed" in item.lower() or citation_re.search(item),
                f"unsourced number(s) {numbers} in acceptance criterion not cited to a "
                f"file:line or marked as a proposal: {item!r}",
            )

    def test_diff_is_a_real_unified_diff_between_the_two_files(self):
        diff_text = (STORY_ENRICH_EXAMPLE / "story-enriched.diff").read_text(encoding="utf-8")
        self.assertIn("--- story-before.md", diff_text)
        self.assertIn("+++ story-enriched.md", diff_text)
        added = [ln for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln for ln in diff_text.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        self.assertTrue(added and removed, "a real diff has both additions and removals here")


if __name__ == "__main__":
    unittest.main()
