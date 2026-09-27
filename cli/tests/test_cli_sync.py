"""``cortex sync`` and the store — ADR-008 §3.3, §3.5, phase 2.

The command runs against a store of its own (``CORTEX_HOME``) and a release served from this
machine (``release_fixture``). From source it stands for Cortex 9.9.9 (``CORTEX_SOURCE_VERSION``),
so that it may download the fake releases 9.9.7 and 9.9.8. A built binary is a build of no
release, 0.0.0-dev.N, and serves only its own version: the tests that download skip there.
"""

import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import cli_harness as harness  # noqa: E402
from release_fixture import FakeRelease  # noqa: E402

OWN = harness.EXPECTED_VERSION if harness.BINARY else "9.9.9"
DOWNLOADS = unittest.skipIf(harness.BINARY, "a build of no release downloads no version")
AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
TREES = ["agents", "docs", "templates"]


def display(path):
    return str(path).replace(os.sep, "/")


def snapshot(root):
    """Everything under ``root``: files as bytes, links as their target."""
    if os.path.islink(root):
        return {".": ("link", os.readlink(root))}
    if root.is_file():
        return {".": root.read_bytes()}
    return {str(p.relative_to(root)): (("link", os.readlink(p)) if p.is_symlink() else
                                       p.read_bytes() if p.is_file() else "dir")
            for p in sorted(root.rglob("*"))}


def is_junction(path):
    return getattr(os.lstat(path), "st_reparse_tag", None) == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1)


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-sync-")).resolve()
        self.addCleanup(self.cleanup)
        self.home = self.tmp / "cortex-home"
        self.release = FakeRelease(("9.9.7", "9.9.8"))
        self.addCleanup(self.release.close)
        self.env = harness.environment(CORTEX_HOME=str(self.home), CORTEX_RELEASES_URL=self.release.url,
                                       CORTEX_SOURCE_VERSION=OWN)

    def cleanup(self):
        for directory, subdirs, files in os.walk(self.tmp):
            for name in subdirs + files:
                path = os.path.join(directory, name)
                if not os.path.islink(path):
                    os.chmod(path, 0o700 if os.path.isdir(path) else 0o600)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def project(self, name="app", version=OWN, extra=""):
        root = self.tmp / name
        root.mkdir(parents=True)
        (root / "cortex.toml").write_text(f'version = "{version}"\ntheme = "h2g2"\n{extra}', encoding="utf-8")
        return root

    def sync(self, project, *args, cwd=None):
        proc = harness.run("sync", *args, cwd=cwd or project, env=self.env)
        proc.out, proc.err = proc.stdout.decode(), proc.stderr.decode()
        return proc

    def validate(self, project, *args):
        proc = harness.run("validate", *args, cwd=project, env=self.env)
        proc.out, proc.err = proc.stdout.decode(), proc.stderr.decode()
        return proc

    def spec(self, project):
        text = (project / "cortex.local.toml").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("spec = "))
        return line.split('"')[1]

    def stored(self, version=OWN):
        return self.home / "versions" / version

    def assert_ok(self, proc):
        self.assertEqual(proc.returncode, 0, proc.err)


class StoreModeTests(SyncTestCase):
    def test_its_own_version_is_written_from_itself_without_a_network(self):
        project = self.project()
        proc = self.sync(project)
        self.assert_ok(proc)
        self.assertIn("written to the store, from this cortex", proc.out)
        self.assertEqual(sorted(p.name for p in self.stored().iterdir()), TREES)
        self.assertTrue((self.stored() / "agents" / "roles" / "prompt-manager.md").is_file())
        self.assertEqual(self.release.requested, [])
        self.assertEqual(self.spec(project), display(self.stored()))

    def test_it_writes_nothing_in_the_project_but_cortex_local_toml(self):
        project = self.project()
        before = sorted(p.name for p in project.iterdir())
        self.assert_ok(self.sync(project))
        self.assertEqual(sorted(p.name for p in project.iterdir()), sorted(before + ["cortex.local.toml"]))

    def test_a_second_sync_finds_it_stored(self):
        project = self.project()
        self.sync(project)
        proc = self.sync(project)
        self.assert_ok(proc)
        self.assertIn("in the store", proc.out)

    def test_a_subdirectory_finds_its_project(self):
        project = self.project()
        deep = project / "src" / "deep"
        deep.mkdir(parents=True)
        self.assert_ok(self.sync(project, cwd=deep))
        self.assertTrue((project / "cortex.local.toml").is_file())
        self.assertFalse((deep / "cortex.local.toml").exists())

    def test_the_developers_theme_and_comments_are_kept(self):
        project = self.project()
        (project / "cortex.local.toml").write_text('# mine\ntheme = "star-wars"  # yes\n', encoding="utf-8")
        self.assert_ok(self.sync(project))
        text = (project / "cortex.local.toml").read_text(encoding="utf-8")
        self.assertTrue(text.startswith('# mine\ntheme = "star-wars"  # yes\nspec = "'), text)

    @DOWNLOADS
    def test_two_projects_on_two_versions_and_a_third_that_downloads_nothing(self):
        first, second, third = self.project("a", "9.9.8"), self.project("b", "9.9.7"), self.project("c", "9.9.8")
        for project in (first, second):
            proc = self.sync(project)
            self.assert_ok(proc)
            self.assertIn("downloaded to the store, checked against its SHA256SUMS", proc.out)
        self.assertEqual(self.spec(first), display(self.stored("9.9.8")))
        self.assertEqual(self.spec(second), display(self.stored("9.9.7")))
        self.assertIn("Cortex 9.9.8", (self.stored("9.9.8") / "agents/roles/prompt-manager.md").read_text(encoding="utf-8"))
        requested = self.release.requested
        proc = self.sync(third)
        self.assert_ok(proc)
        self.assertIn("in the store", proc.out)
        self.assertEqual(self.release.requested, requested)

    @DOWNLOADS
    def test_a_spec_whose_checksum_differs_is_refused_and_leaves_nothing(self):
        self.release.alter_one_byte("spec", "9.9.8")
        proc = self.sync(self.project(version="9.9.8"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("does not match its checksum", proc.err)
        self.assertEqual(list((self.home / "versions").iterdir()), [])

    @DOWNLOADS
    def test_an_archive_leaving_its_tree_is_refused_and_leaves_nothing(self):
        for name in ("../escape.md", "/etc/cortex.md", "agents/../../escape.md"):
            with self.subTest(member=name):
                self.release.replace_spec("9.9.8", {name: b"x"})
                proc = self.sync(self.project(f"p{len(name)}", "9.9.8"))
                self.assertEqual(proc.returncode, 1)
                self.assertIn("which a spec archive cannot hold", proc.err)
                self.assertEqual(list((self.home / "versions").iterdir()), [])
                self.assertFalse((self.tmp / "escape.md").exists())

    @DOWNLOADS
    def test_a_release_without_a_spec_archive_is_refused(self):
        sums = self.release.root / "download" / "9.9.8" / "SHA256SUMS"
        sums.write_text("".join(l for l in sums.read_text().splitlines(True) if "cortex-spec" not in l))
        proc = self.sync(self.project(version="9.9.8"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("lists no cortex-spec.tar.gz", proc.err)

    def test_a_version_newer_than_the_binary_is_refused_with_the_upgrade_command(self):
        proc = self.sync(self.project(version="99.0.0"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn(f"newer than this cortex, {OWN}", proc.err)
        self.assertIn("install.ps1" if os.name == "nt" else "install.sh | sh -s -- 99.0.0", proc.err)
        self.assertFalse(self.home.exists() and any((self.home / "versions").iterdir()))

    @DOWNLOADS
    def test_a_version_before_the_first_spec_archive_is_refused(self):
        proc = self.sync(self.project(version="0.10.1"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("has no spec archive: the first one is 1.0.0", proc.err)
        self.assertEqual(self.release.requested, [])


@unittest.skipIf(AS_ROOT, "root writes any file")
class ReadOnlyStoreTests(SyncTestCase):
    def assert_cannot_write(self, path):
        with self.assertRaises(PermissionError):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("edited through a project\n")
        with self.assertRaises(PermissionError):
            os.remove(path)

    def test_a_file_of_the_store_cannot_be_written_in_place(self):
        project = self.project()
        self.assert_ok(self.sync(project))
        self.assert_cannot_write(self.stored() / "agents" / "roles" / "prompt-manager.md")

    def test_nor_through_the_link(self):
        project = self.project()
        self.assert_ok(self.sync(project, "--link"))
        self.assert_cannot_write(project / "cortex" / "agents" / "roles" / "prompt-manager.md")

    def test_nor_in_a_copy(self):
        project = self.project()
        self.assert_ok(self.sync(project, "--copy"))
        self.assert_cannot_write(project / "cortex" / "agents" / "roles" / "prompt-manager.md")

    @unittest.skipIf(os.name == "nt", "on Windows a read-only directory still takes new files — ADR-008 §9")
    def test_nor_can_a_file_be_added(self):
        project = self.project()
        self.assert_ok(self.sync(project))
        with self.assertRaises(PermissionError):
            (self.stored() / "agents" / "roles" / "new.md").write_text("x", encoding="utf-8")


class ForeignCortexTests(SyncTestCase):
    """Sync never deletes what it did not write — a submodule, a clone, any directory, in every mode."""

    def foreign(self, project, kind):
        cortex = project / "cortex"
        if kind == "file":
            cortex.write_text("mine\n", encoding="utf-8")
            return cortex
        (cortex / "agents").mkdir(parents=True)
        (cortex / "agents" / "notes.md").write_text("mine\n", encoding="utf-8")
        if kind == "submodule":
            (cortex / ".git").write_text("gitdir: ../.git/modules/cortex\n", encoding="utf-8")
        elif kind == "clone":
            (cortex / ".git").mkdir()
            (cortex / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        return cortex

    def test_refused_and_untouched_in_every_mode(self):
        described = {"submodule": "a git submodule", "clone": "a git clone", "directory": "a directory", "file": "a file"}
        for kind, words in described.items():
            for mode in ("--store", "--link", "--copy"):
                with self.subTest(kind=kind, mode=mode):
                    project = self.project(f"{kind}{mode}")
                    cortex = self.foreign(project, kind)
                    before = snapshot(cortex)
                    proc = self.sync(project, mode)
                    self.assertEqual(proc.returncode, 1)
                    self.assertIn(f"cortex/ is {words}, which cortex sync did not write", proc.err)
                    self.assertEqual(snapshot(cortex), before)
                    self.assertFalse((project / "cortex.local.toml").exists())

    @unittest.skipIf(os.name == "nt", "a symbolic link needs a privilege on Windows")
    def test_a_link_it_did_not_make_is_refused(self):
        project = self.project()
        elsewhere = self.tmp / "my-cortex"
        (elsewhere / "agents").mkdir(parents=True)
        (project / "cortex").symlink_to(elsewhere, target_is_directory=True)
        proc = self.sync(project, "--link")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("which cortex sync did not make", proc.err)
        self.assertEqual(os.readlink(project / "cortex"), str(elsewhere))


class LinkAndCopyTests(SyncTestCase):
    def assert_link_to(self, project, target):
        link = project / "cortex"
        if os.name == "nt":
            self.assertTrue(is_junction(link), "a junction, which needs no privilege")
        else:
            self.assertTrue(link.is_symlink())
        self.assertEqual(os.path.realpath(link), os.path.realpath(target))

    def test_link(self):
        project = self.project()
        proc = self.sync(project, "--link")
        self.assert_ok(proc)
        self.assert_link_to(project, self.stored())
        self.assertEqual(self.spec(project), "cortex")
        self.assertIn("note: cortex/ is not in", proc.err)

    def test_back_to_store_removes_the_link_and_only_it(self):
        project = self.project()
        self.sync(project, "--link")
        store_before = snapshot(self.stored())
        self.assert_ok(self.sync(project, "--store"))
        self.assertFalse(os.path.lexists(project / "cortex"))
        self.assertEqual(snapshot(self.stored()), store_before)
        self.assertEqual(self.spec(project), display(self.stored()))

    def test_copy(self):
        project = self.project()
        (project / ".gitignore").write_text("/cortex/\n", encoding="utf-8")
        proc = self.sync(project, "--copy")
        self.assert_ok(proc)
        copy = project / "cortex"
        self.assertFalse(os.path.islink(copy))
        self.assertEqual(sorted(p.name for p in copy.iterdir()), sorted(TREES + [".synced"]))
        self.assertEqual((copy / ".synced").read_text(encoding="utf-8").split("\n")[0], OWN)
        self.assertEqual(self.spec(project), "cortex")
        self.assertNotIn("note:", proc.err)

    def test_back_to_store_removes_the_copy_and_only_it(self):
        project = self.project()
        (project / "notes.md").write_text("mine\n", encoding="utf-8")
        self.sync(project, "--copy")
        self.assert_ok(self.sync(project))
        self.assertEqual(sorted(p.name for p in project.iterdir()), ["cortex.local.toml", "cortex.toml", "notes.md"])
        self.assertTrue(self.stored().is_dir())

    def test_cortex_toml_sets_the_mode_and_a_flag_overrides_it(self):
        project = self.project(extra='sync = "copy"\n')
        self.assert_ok(self.sync(project))
        self.assertTrue((project / "cortex" / ".synced").is_file())
        self.assert_ok(self.sync(project, "--link"))
        self.assert_link_to(project, self.stored())

    @DOWNLOADS
    def test_a_new_version_moves_the_link(self):
        project = self.project(version="9.9.7", extra='sync = "link"\n')
        self.assert_ok(self.sync(project))
        (project / "cortex.toml").write_text('version = "9.9.8"\ntheme = "h2g2"\nsync = "link"\n', encoding="utf-8")
        self.assert_ok(self.sync(project))
        self.assert_link_to(project, self.stored("9.9.8"))

    @DOWNLOADS
    def test_a_new_version_replaces_the_copy(self):
        project = self.project(version="9.9.7", extra='sync = "copy"\n')
        self.assert_ok(self.sync(project))
        (project / "cortex.toml").write_text('version = "9.9.8"\ntheme = "h2g2"\nsync = "copy"\n', encoding="utf-8")
        self.assert_ok(self.sync(project))
        self.assertIn("Cortex 9.9.8", (project / "cortex/agents/roles/prompt-manager.md").read_text(encoding="utf-8"))


class FromTests(SyncTestCase):
    def test_spec_names_the_checkout_and_a_warning_says_so_every_time(self):
        project = self.project()
        for _ in range(2):
            proc = self.sync(project, "--from", str(harness.REPO))
            self.assert_ok(proc)
            self.assertIn("no version is checked (--from)", proc.err)
        self.assertEqual(self.spec(project), display(harness.REPO))
        self.assertFalse(self.home.exists())

    def test_validate_reads_the_checkouts_base(self):
        project = self.project()
        self.sync(project, "--from", str(harness.REPO))
        proc = self.validate(project)
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn(f"Cortex dir:    {display(harness.REPO)}", proc.out)

    def test_a_directory_that_is_no_checkout_is_refused(self):
        project = self.project()
        proc = self.sync(project, "--from", str(self.tmp))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no Cortex checkout there", proc.err)


class ProjectFileTests(SyncTestCase):
    def test_no_cortex_toml(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        proc = self.sync(bare)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no cortex.toml in", proc.err)
        self.assertIn("cortex init", proc.err)

    def test_a_bad_cortex_toml_writes_nothing(self):
        project = self.project(extra='verison = "1.2.3"\n')
        proc = self.sync(project)
        self.assertEqual(proc.returncode, 1)
        self.assertIn('unknown key "verison"', proc.err)
        self.assertFalse((project / "cortex.local.toml").exists())
        self.assertFalse(self.home.exists())

    def test_a_bad_cortex_local_toml_is_refused(self):
        project = self.project()
        (project / "cortex.local.toml").write_text('version = "1.0.0"\n', encoding="utf-8")
        proc = self.sync(project)
        self.assertEqual(proc.returncode, 1)
        self.assertIn('unknown key "version"', proc.err)
        self.assertIn("theme and spec only", proc.err)

    def test_two_modes_at_once_are_a_bad_argument(self):
        proc = self.sync(self.project(), "--link", "--copy")
        self.assertEqual(proc.returncode, 2)

    def test_an_unknown_theme_is_said(self):
        project = self.project()
        (project / "cortex.local.toml").write_text('theme = "no-such-theme"\n', encoding="utf-8")
        proc = self.sync(project)
        self.assert_ok(proc)
        self.assertIn('theme "no-such-theme" is neither in the spec nor in agents/personalities/', proc.err)


class ValidateTests(SyncTestCase):
    def test_validate_reads_the_synced_spec(self):
        project = self.project()
        self.sync(project)
        proc = self.validate(project, "--strict")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn(f"Cortex dir:    {display(self.stored())}", proc.out)
        self.assertIn(f"Project root:  {display(project)}", proc.out)

    def test_validate_before_sync(self):
        proc = self.validate(self.project())
        self.assertEqual(proc.returncode, 2)
        self.assertIn("names no spec yet — run `cortex sync`", proc.err)

    @DOWNLOADS
    def test_validate_refuses_a_spec_synced_for_another_version(self):
        for mode in ("store", "link", "copy"):
            with self.subTest(mode=mode):
                project = self.project(f"p-{mode}", "9.9.7", f'sync = "{mode}"\n')
                self.assert_ok(self.sync(project))
                (project / "cortex.toml").write_text(f'version = "9.9.8"\ntheme = "h2g2"\nsync = "{mode}"\n',
                                                     encoding="utf-8")
                proc = self.validate(project)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("pins Cortex 9.9.8, and the spec synced is 9.9.7", proc.err)


if __name__ == "__main__":
    unittest.main()
