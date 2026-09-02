"""Pin the worked example in projectdir's module docstring.

The docstring documents the cwd -> Claude-project-slug transformation with a
concrete example. It previously used a real OS account name; it now uses the
`alice` placeholder that scripts/check_identifiers.py sanctions. This test keeps
the example *true* as well as neutral, so the next edit to it cannot quietly
drift away from what slug_for_cwd actually does.
"""
import unittest

from tests._util import TempHomeTest  # noqa: F401  (import root side effect)
from morpheus.lib import projectdir

EXAMPLE_CWD = "C:" + "\\" + "Users" + "\\" + "alice" + "\\" + "repo"
EXAMPLE_SLUG = "C--Users-alice-repo"


class SlugExampleTest(unittest.TestCase):
    def test_docstring_example_is_accurate(self):
        self.assertEqual(projectdir.slug_for_cwd(EXAMPLE_CWD), EXAMPLE_SLUG)

    def test_docstring_actually_contains_that_example(self):
        doc = projectdir.__doc__ or ""
        self.assertIn(EXAMPLE_SLUG, doc)
        self.assertIn("alice", doc)

    def test_posix_cwd_slugifies_too(self):
        self.assertEqual(projectdir.slug_for_cwd("/home/alice/repo"), "-home-alice-repo")

    def test_empty_cwd_is_tolerated(self):
        self.assertEqual(projectdir.slug_for_cwd(""), "")


if __name__ == "__main__":
    unittest.main()
