"""``cortex.toml``, ``cortex.local.toml`` and versions — ADR-008 §3.3, §3.4."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2] / "core")]
from cortex_cli import config  # noqa: E402
from cortex_cli.semver import FIRST_SPEC_ARCHIVE, Version  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_semver_precedence(self):
        # The example of semver.org §11, and builds of no release.
        ordered = ["0.0.0-dev", "0.0.0-dev.3", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                   "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "1.10.0", "2.0.0"]
        self.assertEqual([str(v) for v in sorted(map(Version, reversed(ordered)))], ordered)

    def test_what_is_no_version(self):
        for text in ("1.0", "v1.0.0", "01.0.0", "1.0.0+build", "1.0.0-", "1.0.0-01", "latest", "", "1.0.0 ",
                     "1.0.0\n", "\u0661.0.0"):
            with self.subTest(text=text):
                self.assertFalse(Version.valid(text))
                with self.assertRaises(ValueError):
                    Version(text)

    def test_the_first_spec_archive(self):
        self.assertEqual(FIRST_SPEC_ARCHIVE, Version("1.0.0"))
        self.assertLess(Version("1.0.0-rc.1"), FIRST_SPEC_ARCHIVE)


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cortex-config-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def assert_refused(self, *fragments):
        with self.assertRaises(config.ConfigError) as caught:
            config.load(str(self.root))
        for fragment in fragments:
            self.assertIn(fragment, str(caught.exception))


class ProjectFileTests(ConfigTestCase):
    def test_the_two_required_keys(self):
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\n')
        project = config.load(str(self.root))
        self.assertEqual((str(project.version), project.theme, project.sync), ("1.0.0", "h2g2", None))

    def test_sync_is_optional_and_one_of_three(self):
        for mode in ("store", "link", "copy"):
            self.write("cortex.toml", f'version = "1.0.0"\ntheme = "h2g2"\nsync = "{mode}"\n')
            self.assertEqual(config.load(str(self.root)).sync, mode)
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\nsync = "symlink"\n')
        self.assert_refused('sync "symlink"', "store, link and copy")

    def test_an_unknown_key_is_refused_and_named(self):
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\nverison = "1.1.0"\n')
        self.assert_refused('unknown key "verison"', "version, theme, sync and claude_access")

    def test_a_table_is_an_unknown_key(self):
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\n[models]\ndefault = "x"\n')
        self.assert_refused('unknown key "models"')

    def test_version_and_theme_are_required(self):
        for text, key in (('theme = "h2g2"\n', "version"), ('version = "1.0.0"\n', "theme")):
            with self.subTest(missing=key):
                self.write("cortex.toml", text)
                self.assert_refused(f'"{key}" is required')

    def test_values_are_strings(self):
        self.write("cortex.toml", 'version = 1.0\ntheme = "h2g2"\n')
        self.assert_refused('"version" must be a string')

    def test_a_version_that_is_none(self):
        self.write("cortex.toml", 'version = "1.0"\ntheme = "h2g2"\n')
        self.assert_refused('version "1.0" is no version')

    def test_a_theme_is_a_name_not_a_path(self):
        for theme in ("../evil", "a/b", ".hidden", "a b", "h2g2\\n"):
            with self.subTest(theme=theme):
                self.write("cortex.toml", f'version = "1.0.0"\ntheme = "{theme}"\n')
                self.assert_refused("is no theme name")

    def test_invalid_toml_names_the_file(self):
        self.write("cortex.toml", 'version = "1.0.0\n')
        self.assert_refused("cortex.toml:")

    def test_a_byte_order_mark_and_crlf_are_read(self):
        (self.root / "cortex.toml").write_bytes(b'\xef\xbb\xbfversion = "1.0.0"\r\ntheme = "none"\r\n')
        self.assertEqual(config.load(str(self.root)).theme, "none")


class LocalFileTests(ConfigTestCase):
    def setUp(self):
        super().setUp()
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\n')

    def test_it_is_optional(self):
        project = config.load(str(self.root))
        self.assertIsNone(project.spec)
        self.assertEqual(project.active_theme, "h2g2")

    def test_its_theme_overrides_the_teams(self):
        self.write("cortex.local.toml", 'theme = "star-wars"\n')
        self.assertEqual(config.load(str(self.root)).active_theme, "star-wars")

    def test_only_theme_spec_and_claude_access(self):
        for key in ("version", "sync", "specs"):
            with self.subTest(key=key):
                self.write("cortex.local.toml", f'{key} = "x"\n')
                self.assert_refused(f'unknown key "{key}"', "theme, spec and claude_access only")

    def test_claude_access_is_the_teams_unless_the_developer_says(self):
        self.assertFalse(config.load(str(self.root)).active_claude_access)
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\nclaude_access = true\n')
        self.assertTrue(config.load(str(self.root)).active_claude_access)
        self.write("cortex.local.toml", "claude_access = false\n")
        self.assertFalse(config.load(str(self.root)).active_claude_access)

    def test_claude_access_is_a_boolean(self):
        self.write("cortex.local.toml", 'claude_access = "yes"\n')
        self.assert_refused('"claude_access" must be true or false, without quotes')

    def test_spec_relative_or_absolute(self):
        self.write("cortex.local.toml", 'spec = "cortex"\n')
        self.assertEqual(config.load(str(self.root)).spec_directory(), f"{self.root}/cortex")
        absolute = str(self.root / "elsewhere")
        self.write("cortex.local.toml", f"spec = {config.toml_string(absolute)}\n")
        self.assertEqual(config.load(str(self.root)).spec_directory(), absolute)


class WriteSpecTests(ConfigTestCase):
    def read(self):
        return (self.root / "cortex.local.toml").read_text(encoding="utf-8")

    def test_a_new_file(self):
        config.write_spec(str(self.root), "/home/dev/.cortex/versions/1.0.0")
        self.assertTrue(self.read().startswith("# This developer, on this machine"))
        self.assertIn('spec = "/home/dev/.cortex/versions/1.0.0"', self.read())

    def test_every_other_line_is_kept_verbatim(self):
        before = '# my own comment\ntheme = "star-wars"   # I like it\n\nspec = "/old/path"  # stale\n# trailing\n'
        self.write("cortex.local.toml", before)
        config.write_spec(str(self.root), "/new/path")
        # The comment that ends the line rewritten is kept too — the developer's, or sync's own.
        self.assertEqual(self.read(), before.replace('spec = "/old/path"  # stale', 'spec = "/new/path"  # stale'))

    def test_a_byte_order_mark_and_a_comment_after_a_value_stay(self):
        (self.root / "cortex.local.toml").write_bytes(
            '\ufefftheme = "a#b"  # mine, with a "#" in the value\r\nspec = "/old"\r\n'.encode("utf-8"))
        config.write_spec(str(self.root), "/new")
        self.assertEqual((self.root / "cortex.local.toml").read_bytes().decode("utf-8"),
                         '\ufefftheme = "a#b"  # mine, with a "#" in the value\r\n'
                         'spec = "/new"    # written by `cortex sync`\r\n')

    def test_spec_is_added_when_missing(self):
        self.write("cortex.local.toml", 'theme = "none"')          # no final newline
        config.write_spec(str(self.root), "cortex")
        self.assertEqual(self.read(), 'theme = "none"\nspec = "cortex"    # written by `cortex sync`\n')

    def test_crlf_stays_crlf(self):
        (self.root / "cortex.local.toml").write_bytes(b'theme = "none"\r\nspec = "x"\r\n')
        config.write_spec(str(self.root), "y")
        self.assertEqual((self.root / "cortex.local.toml").read_bytes(),
                         b'theme = "none"\r\nspec = "y"    # written by `cortex sync`\r\n')

    def test_a_windows_path_is_escaped(self):
        config.write_spec(str(self.root), 'C:\\Users\\dev "q"\\.cortex')
        self.write("cortex.toml", 'version = "1.0.0"\ntheme = "h2g2"\n')
        self.assertEqual(config.load(str(self.root)).spec, 'C:\\Users\\dev "q"\\.cortex')

    def test_a_boolean_is_written_without_quotes_and_rewritten_in_place(self):
        self.write("cortex.local.toml", 'theme = "none"\nclaude_access = false  # mine\n')
        config.write_local(str(self.root), "claude_access", True)
        self.assertEqual(self.read(), 'theme = "none"\nclaude_access = true\n')

    def test_a_spec_it_cannot_rewrite_is_refused_and_the_file_kept(self):
        before = 'spec = """\n/old\n"""\n'
        self.write("cortex.local.toml", before)
        with self.assertRaises(config.ConfigError):
            config.write_spec(str(self.root), "/new")
        self.assertEqual(self.read(), before)


class FindProjectTests(ConfigTestCase):
    def test_the_nearest_ancestor(self):
        self.write("cortex.toml", "")
        deep = self.root / "a" / "b"
        deep.mkdir(parents=True)
        self.assertEqual(config.find_project(str(deep)), str(self.root))

    def test_none(self):
        self.assertIsNone(config.find_project(str(self.root)))


if __name__ == "__main__":
    unittest.main()
