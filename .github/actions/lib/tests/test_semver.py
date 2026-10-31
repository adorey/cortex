"""The actions' SemVer ordering, against the table the CLI is checked against too."""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from semver import Version, highest, is_prerelease, is_release  # noqa: E402

CASES = json.loads((HERE / "semver-cases.json").read_text(encoding="utf-8"))


class TableTests(unittest.TestCase):
    def test_the_ordered_versions(self):
        ordered = CASES["ordered"]
        self.assertEqual([str(v) for v in sorted(map(Version, reversed(ordered)))], ordered)

    def test_each_neighbour_is_strictly_higher(self):
        versions = [Version(text) for text in CASES["ordered"]]
        for lower, higher in zip(versions, versions[1:]):
            with self.subTest(lower=str(lower), higher=str(higher)):
                self.assertLess(lower, higher)
                self.assertNotEqual(lower, higher)

    def test_the_sort_v_counterexample(self):
        case = CASES["sort_v_counterexample"]
        self.assertLess(Version(case["lower"]), Version(case["higher"]))

    def test_what_is_no_version(self):
        for text in CASES["invalid"]:
            with self.subTest(text=text):
                self.assertIsNone(Version.parse(text))
                with self.assertRaises(ValueError):
                    Version(text)


class KindTests(unittest.TestCase):
    def test_releases(self):
        self.assertTrue(is_release("1.3.0"))
        for text in ("1.3.0-rc.1", "v1.3.0", "1.3", None):
            with self.subTest(text=text):
                self.assertFalse(is_release(text))

    def test_prereleases_as_they_are_cut(self):
        for text in ("1.3.0-alpha.1", "1.3.0-beta.2", "1.3.0-rc.10"):
            with self.subTest(text=text):
                self.assertTrue(is_prerelease(text))
        for text in ("1.3.0-rc1", "1.3.0-RC.1", "1.3.0-rc.01", "1.3.0-preview.1", "1.3.0", "1.3.0-rc"):
            with self.subTest(text=text):
                self.assertFalse(is_prerelease(text))

    def test_the_release_a_prerelease_prepares(self):
        self.assertEqual(Version("1.3.0-rc.2").release, Version("1.3.0"))
        self.assertEqual(Version("2.0.0").major, 2)

    def test_highest(self):
        self.assertEqual(highest(map(Version, ["1.2.0", "2.0.0-alpha.1", "1.10.0"])), Version("2.0.0-alpha.1"))
        self.assertIsNone(highest([]))


if __name__ == "__main__":
    unittest.main()
