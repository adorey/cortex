"""Reading a changelog and its notes."""

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from changelog import DEFAULT_SECTION, first_after_unreleased, has_section, headings, note_version, section_text  # noqa: E402

TEXT = """# Changelog

## [Unreleased]

### Added
- a thing

## [1.4.0] - 2026-11-03 — A Name _(Released)_
[Full notes](changelog/1.4.0.md)

### Fixed
- another

## [1.3.0] - 2026-11-01 — Older _(Released)_
"""


class ChangelogTests(unittest.TestCase):
    def test_headings_in_order(self):
        self.assertEqual([label for label, _ in headings(TEXT)], ["Unreleased", "1.4.0", "1.3.0"])

    def test_the_first_section_after_unreleased(self):
        self.assertEqual(first_after_unreleased(TEXT), "## [1.4.0] - 2026-11-03 — A Name _(Released)_")
        self.assertEqual(first_after_unreleased("## [2.0.0] - 2026-01-01 — X _(Released)_"),
                         "## [2.0.0] - 2026-01-01 — X _(Released)_")
        self.assertIsNone(first_after_unreleased("# Changelog\n\n## [Unreleased]\n"))

    def test_the_default_section_reads_version_and_date(self):
        match = re.fullmatch(DEFAULT_SECTION, first_after_unreleased(TEXT))
        self.assertEqual((match.group("version"), match.group("date"), match.group("name")), ("1.4.0", "2026-11-03", "A Name"))
        self.assertIsNone(re.fullmatch(DEFAULT_SECTION, "## [1.4.0] - 2026-11-03 — A Name"))

    def test_has_section(self):
        self.assertTrue(has_section(TEXT, "1.3.0"))
        self.assertFalse(has_section(TEXT, "1.3"))

    def test_a_section_body(self):
        self.assertEqual(section_text(TEXT, "Unreleased"), "### Added\n- a thing")
        self.assertEqual(section_text(TEXT, "1.3.0"), "")
        self.assertIsNone(section_text(TEXT, "9.9.9"))

    def test_note_versions(self):
        self.assertEqual(note_version("changelog/1.4.0.md", "changelog"), "1.4.0")
        self.assertEqual(note_version("docs/notes/1.4.0.md", "docs/notes/"), "1.4.0")
        for path in ("changelog/1.4.0-rc.1.md", "changelog/README.md", "changelog/old/1.0.0.md",
                     "other/1.4.0.md", "changelog/01.4.0.md"):
            with self.subTest(path=path):
                self.assertIsNone(note_version(path, "changelog"))


@unittest.skipUnless((HERE.parents[3] / "CHANGELOG.md").is_file(), "not in the repository that calls the actions")
class ThisRepositoryTests(unittest.TestCase):
    def test_every_released_section_of_this_changelog_has_the_default_shape(self):
        text = (HERE.parents[3] / "CHANGELOG.md").read_text(encoding="utf-8")
        released = [line for label, line in headings(text) if label != "Unreleased"]
        self.assertGreater(len(released), 10)
        for line in released[:12]:
            with self.subTest(line=line):
                self.assertIsNotNone(re.fullmatch(DEFAULT_SECTION, line))


if __name__ == "__main__":
    unittest.main()
