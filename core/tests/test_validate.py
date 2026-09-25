"""The validator's checks, tier by tier, against the verdicts captured from the script."""

import io
import json
import ntpath
import os
import subprocess
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_core.validate import (  # noqa: E402
    Colors, Report, check_overlay, find, main, overlay_roots, shown, validate,
)
from tests import validator_harness as harness  # noqa: E402

EXPECTED = json.loads(harness.EXPECTED.read_text(encoding="utf-8"))

TIER_1 = ["ok-additive", "ok-replacement", "custom-addition", "header-after-line-10", "crlf",
          "absent-base-key", "absent-scope-key", "absent-semantic-key",
          "empty-base-value", "empty-scope-value", "empty-semantic-value",
          "base-not-found", "invalid-semantic", "escape-in-field", "replacement-outside-workflows", "path-mirror"]


def captured_verdicts(case):
    """The verdict lines the script printed for ``case``: what follows its scope header."""
    lines = EXPECTED[case]["default"]["stdout"]
    start = next(i for i, line in enumerate(lines) if line.startswith("── Scope: ")) + 1
    return lines[start:lines.index("", start)]


def core_verdicts(case):
    tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
    try:
        project = harness.layout(case, tmp)
        overlays = sorted(p for p in project.rglob("*.md")
                          if p.relative_to(project).parts[0] != "cortex" and p.name != "project-overview.md")
        out = io.StringIO()
        report = Report(out, Colors(False))
        for path in overlays:
            parts = path.relative_to(project).parts
            root = project.joinpath(*parts[:parts.index("agents")])
            check_overlay(str(path), str(root), str(project), str(project / "cortex"), report)
        return report, out.getvalue().split("\n")[:-1]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class VerdictTestCase(unittest.TestCase):
    def assert_case(self, case):
        _, lines = core_verdicts(case)
        self.assertEqual(lines, captured_verdicts(case))


class Tier1Tests(VerdictTestCase):
    def test_every_tier_1_case_gets_its_captured_verdicts(self):
        for case in TIER_1:
            with self.subTest(case=case):
                self.assert_case(case)


TIER_2 = ["non-overridable", "sections-untagged", "scope-service-at-root", "scope-workspace-in-service",
          # a service overlay straight under its layer directory, with no category level (#84)
          "scope-workspace-in-service-shallow"]


class Tier2Tests(VerdictTestCase):
    def test_every_tier_2_case_gets_its_captured_verdicts(self):
        for case in TIER_2:
            with self.subTest(case=case):
                self.assert_case(case)


OVERLAY = ("<!-- OVERLAY\n     Base: cortex/agents/roles/engineering/lead-backend.md\n     Scope: workspace\n"
           "     Semantic: additive\n-->\n\n## Naming (additive)\n- a project rule\n")


class SymlinkTests(unittest.TestCase):
    """Symbolic links, where the port parts from the script on purpose (ADR-007 §9)."""

    def project(self):
        """A host project, and an overlay kept outside its agents/ directory."""
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = tmp / "host"
        shutil.copytree(harness.FIXTURES / "base", project / "cortex")
        overlay = tmp / "shared" / "roles" / "engineering" / "lead-backend.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_text(OVERLAY, encoding="utf-8")
        return project, overlay

    def run_validator(self, project):
        out = io.StringIO()
        validate(str(project), str(project / "cortex"), "", False, out, Colors(False))
        return out.getvalue()

    def test_a_layer_directory_reached_through_a_link_is_validated(self):
        # The resolver reads through the link, so the validator checks what it reads. GNU find -P,
        # which the script ran, did not enter a starting point that is a link: "Checked: 0 files".
        project, overlay = self.project()
        (project / "agents").mkdir()
        (project / "agents" / "roles").symlink_to(overlay.parent.parent, target_is_directory=True)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", self.run_validator(project))

    def test_an_overlay_file_that_is_a_link_is_validated(self):
        # The resolver reads the file behind the link; find -type f, as the script ran it, skipped it.
        project, overlay = self.project()
        (project / "agents" / "roles" / "engineering").mkdir(parents=True)
        (project / "agents" / "roles" / "engineering" / "lead-backend.md").symlink_to(overlay)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", self.run_validator(project))

    def test_a_subdirectory_that_is_a_link_is_validated(self):
        project, overlay = self.project()
        (project / "agents" / "roles").mkdir(parents=True)
        (project / "agents" / "roles" / "engineering").symlink_to(overlay.parent, target_is_directory=True)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", self.run_validator(project))

    def test_a_link_loop_is_entered_once(self):
        project, overlay = self.project()
        (project / "agents").mkdir()
        (project / "agents" / "roles").symlink_to(overlay.parent.parent, target_is_directory=True)
        (overlay.parent / "again").symlink_to(overlay.parent.parent, target_is_directory=True)
        report = self.run_validator(project)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", report)
        self.assertIn("Checked:  1 files", report)


@unittest.skipIf(shutil.which("find") is None, "find not available")
class DiscoveryTests(unittest.TestCase):
    """What the script's two find calls found, and in which order — asked of find itself, on the
    same file system, so that the guard outlives the script."""

    def tree(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = tmp / "host"
        # Created out of alphabetical order, files and directories mixed, several levels deep.
        for service in ("svc-z", "svc-a", "tools/svc-m"):
            for layer in ("workflows", "roles", "capabilities"):
                for rel in ("zeta.md", "b/deep/x.md", "alpha.md", "b/c.md", "notes.txt", "a/y.md"):
                    path = project / service / "agents" / layer / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# x\n", encoding="utf-8")
            (project / service / "project-overview.md").write_text("# s\n", encoding="utf-8")
        for skipped in (".git/modules/svc-g", "vendor/cortex/svc-c"):
            (project / skipped / "agents").mkdir(parents=True)
            (project / skipped / "project-overview.md").write_text("# s\n", encoding="utf-8")
        return project

    def gnu_find(self, *args):
        out = subprocess.run(["find", *args], capture_output=True, text=True, check=True).stdout
        return out.splitlines()

    def test_layer_files_come_in_finds_order(self):
        project = self.tree()
        for layer_dir in sorted(project.glob("*/agents/*")) + sorted(project.glob("tools/*/agents/*")):
            with self.subTest(layer_dir=str(layer_dir.relative_to(project))):
                self.assertEqual(find(str(layer_dir), "*.md", regular_files=True),
                                 self.gnu_find(str(layer_dir), "-name", "*.md", "-type", "f"))

    def test_services_come_in_finds_order_outside_git_and_cortex(self):
        project = self.tree()
        expected = self.gnu_find(str(project), "-maxdepth", "5", "-name", "project-overview.md",
                                 "-not", "-path", "*/cortex/*", "-not", "-path", "*/.git/*")
        found = [f"{root}/project-overview.md" for root in overlay_roots(str(project), str(project / "cortex"), "")]
        self.assertEqual(found, expected)
        self.assertFalse(any("/.git/" in f or "/cortex/" in f for f in found), found)


class UnreadableFileTests(unittest.TestCase):
    """A file the validator cannot read: the script's head failed, said so on stderr, and the
    file counted as one without a header."""

    def test_an_unreadable_file_is_reported_on_stderr_and_skipped(self):
        err = io.StringIO()
        with mock.patch("cortex_core.validate.read_text", side_effect=PermissionError(13, "Permission denied")), \
                mock.patch("sys.stderr", err):
            _, lines = core_verdicts("custom-addition")
        self.assertEqual(lines, ["ℹ agents/roles/engineering/my-own-role.md (custom addition — no cortex base, skipping overlay checks)"])
        self.assertRegex(err.getvalue(), r"^head: cannot open '.*/agents/roles/engineering/my-own-role.md' for reading: Permission denied\n$")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads any file")
    def test_a_file_without_read_permission(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = harness.layout("custom-addition", tmp)
        overlay = project / "agents" / "roles" / "engineering" / "my-own-role.md"
        overlay.chmod(0)
        self.addCleanup(overlay.chmod, 0o644)
        code, out, err = harness.run_core(project, [])
        self.assertEqual(code, 0)
        self.assertIn(b"custom addition", out)
        self.assertIn(b"Permission denied", err)
        self.assertNotIn(b"Traceback", err)


class ServiceOptionTests(unittest.TestCase):
    def test_an_absolute_service_path_in_windows_form(self):
        # Git Bash hands Python /c/work as C:/work: absolute, though it does not start with "/".
        with mock.patch("os.path.isabs", ntpath.isabs):
            self.assertEqual(overlay_roots("C:/work/host", "C:/work/host/cortex", "C:/work/host/svc-a"),
                             ["C:/work/host/svc-a"])


class MainTests(unittest.TestCase):
    def test_main_leaves_the_process_streams_open(self):
        # In one process — a test, a CLI embedding the core — whatever runs next still writes.
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            self.assertEqual(main(["--help"]), 0)
            self.assertEqual(main(["--no-such-option"]), 2)
        self.assertFalse(stdout.closed)
        self.assertFalse(stderr.closed)
        stdout.write("still open\n")
        stdout.flush()
        self.assertIn(b"Usage: validate-overlays.sh", stdout.buffer.getvalue())
        self.assertIn(b"Unknown argument: --no-such-option", stderr.buffer.getvalue())

class MissingHeaderTests(unittest.TestCase):
    """ADR-007 §3.6 — a file without a header at the path of a base shadows it: it is an overlay."""

    def test_a_headerless_file_at_a_base_path_is_reported(self):
        _, lines = core_verdicts("missing-header")
        self.assertEqual(lines[0], "⚠ agents/roles/engineering/lead-backend.md")
        self.assertTrue(lines[1].startswith("  MISSING_HEADER — "), lines[1])
        self.assertEqual(len(lines), 2)

    def test_a_headerless_file_with_no_base_is_still_a_custom_addition(self):
        _, lines = core_verdicts("custom-addition")
        self.assertEqual(lines, ["ℹ agents/roles/engineering/my-own-role.md (custom addition — no cortex base, skipping overlay checks)"])


class MissingFieldTests(unittest.TestCase):
    """#81 — a header key that is absent is reported like an empty one, and the run goes on."""

    def test_an_absent_key_is_reported(self):
        for case, field in (("absent-base-key", "Base"), ("absent-scope-key", "Scope"), ("absent-semantic-key", "Semantic")):
            with self.subTest(case=case):
                report, lines = core_verdicts(case)
                self.assertIsNotNone(report, "the run was aborted")
                self.assertEqual(lines, ["✗ agents/roles/engineering/lead-backend.md",
                                         f"  MISSING_FIELD — {field}: is required in OVERLAY header"])

    def test_the_other_overlays_are_still_checked(self):
        report, lines = core_verdicts("absent-key-among-others")
        self.assertIsNotNone(report, "the run was aborted")
        self.assertIn("✓ agents/workflows/engineering/code-review.md", lines)
        self.assertEqual((report.errors, report.checked), (1, 2))


class SelfValidationTests(unittest.TestCase):
    """ADR-007 §3.1 — when the base is the project root, its files are the base, not overlays of it."""

    def test_the_base_is_not_an_overlay_of_itself(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        root = tmp / "cortex"
        shutil.copytree(harness.FIXTURES / "base", root)
        out = io.StringIO()
        code = validate(str(root), str(root), "", True, out, Colors(False))
        self.assertNotIn("MISSING_HEADER", out.getvalue())
        self.assertEqual(code, 0)


class PathTests(unittest.TestCase):
    """#84 — the verdicts come from the root being scanned, not from where the project sits."""

    def run_core(self, case, *args):
        return harness.execute(case, list(args), harness.run_core)

    def test_a_project_inside_a_directory_named_agents(self):
        run = self.run_core("project-under-agents-dir")
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", run["stdout"])
        at = run["stdout"].index("⚠ agents/roles/engineering/architect.md")
        self.assertTrue(run["stdout"][at + 1].startswith("  MISSING_HEADER — "), run["stdout"][at + 1])

    def test_a_project_inside_a_directory_named_cortex_has_its_services_checked(self):
        run = self.run_core("project-under-cortex-dir", "--strict")
        self.assertIn("✗ svc-a/agents/roles/engineering/lead-backend.md", run["stdout"])
        self.assertEqual(run["code"], 1)

    def test_a_replacement_outside_workflows_under_an_agents_workflows_directory(self):
        run = self.run_core("replacement-under-agents-workflows-dir")
        self.assertIn("  REPLACEMENT_OUTSIDE_WORKFLOWS — Semantic: replacement is only allowed for files under agents/workflows/",
                      run["stdout"])

    def test_a_workspace_scope_on_a_service_overlay_with_no_category(self):
        run = self.run_core("scope-workspace-in-service-shallow")
        at = run["stdout"].index("⚠ svc-a/agents/roles/lead-backend.md")
        self.assertTrue(run["stdout"][at + 1].startswith("  SCOPE_MISMATCH — "), run["stdout"][at + 1])

    def test_the_base_is_skipped_by_its_location_whatever_its_name(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project, base = tmp / "host", tmp / "host" / ".cortex"
        for root in (base, base / "tests" / "fixtures" / "host", project / "svc-a"):
            (root / "agents").mkdir(parents=True)
            (root / "project-overview.md").write_text("# overview\n", encoding="utf-8")
        self.assertEqual(overlay_roots(str(project), str(base), ""), [f"{project}/svc-a"])

    def test_a_git_directory_below_the_project_is_still_skipped(self):
        # Not a fixture case: git refuses to track a directory named .git.
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = tmp / "host"
        for root in (project / ".git" / "modules" / "svc-b", project / "svc-a"):
            (root / "agents").mkdir(parents=True)
            (root / "project-overview.md").write_text("# overview\n", encoding="utf-8")
        self.assertEqual(overlay_roots(str(project), str(project / "cortex"), ""), [f"{project}/svc-a"])


class OutputTests(unittest.TestCase):
    """#85 — the validator prints what it read; its colours are the only escapes it emits."""

    def test_the_workspace_section_is_headed_with_a_dot(self):
        run = harness.execute("ok-additive", [], harness.run_core)
        self.assertIn("── Scope: . ──", run["stdout"])

    def test_a_backslash_sequence_in_a_value_is_printed_as_typed(self):
        _, lines = core_verdicts("escape-in-field")
        self.assertEqual(lines[1], "  INVALID_SEMANTIC — Semantic: must be 'additive' or 'replacement' (got 'add\\tive')")

    def test_a_control_character_in_a_value_is_shown_escaped(self):
        _, lines = core_verdicts("control-char-in-field")
        self.assertEqual(lines[1], "  INVALID_SEMANTIC — Semantic: must be 'additive' or 'replacement' (got 'additive\\x1b[2K\\x1b[1A')")

    def test_a_control_character_in_a_file_name_is_shown_escaped(self):
        out = io.StringIO()
        Report(out, Colors(True)).ok("agents/roles/x\x1b[2K.md")
        self.assertEqual(out.getvalue(), "\x1b[0;32m✓\x1b[0m agents/roles/x\\x1b[2K.md\n")
        for verdict, args in (("error", ("CODE", "got '\x1b'")), ("warning", ("CODE", "got '\x1b'")), ("info", ("a note",))):
            with self.subTest(verdict=verdict):
                out = io.StringIO()
                getattr(Report(out, Colors(False)), verdict)("agents/roles/x\x1b[2K.md", *args)
                self.assertNotIn("\x1b", out.getvalue())

    def test_a_backslash_c_no_longer_cuts_the_output(self):
        out = io.StringIO()
        Report(out, Colors(False)).error("agents/roles/x.md", "INVALID_SEMANTIC", "got 'x\\cy'")
        self.assertEqual(out.getvalue(), "✗ agents/roles/x.md\n  INVALID_SEMANTIC — got 'x\\cy'\n")

    def test_control_characters_in_directory_names_are_shown_escaped(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = tmp / "host\x1b[2K"
        shutil.copytree(harness.FIXTURES / "base", project / "cortex")
        overlay = project / "svc\x1b[1A" / "agents" / "roles" / "engineering" / "lead-backend.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_text("<!-- OVERLAY\n     Base: cortex/agents/roles/engineering/lead-backend.md\n"
                           "     Scope: service @svc\n     Semantic: additive\n-->\n## Rules (additive)\n", encoding="utf-8")
        (project / "svc\x1b[1A" / "project-overview.md").write_text("# svc\n", encoding="utf-8")
        for service in ("", "svc\x1b[1A"):
            with self.subTest(service=service):
                out = io.StringIO()
                validate(str(project), str(project / "cortex"), service, False, out, Colors(False))
                self.assertNotIn("\x1b", out.getvalue())
                self.assertIn("✓ svc\\x1b[1A/agents/roles/engineering/lead-backend.md", out.getvalue())

    def test_only_control_characters_are_rewritten(self):
        # Printable text, and a raw byte from a file name that is not valid UTF-8, stay as they are.
        self.assertEqual(shown("\u00e9 — ✓ 🚫 \udce9"), "\u00e9 — ✓ 🚫 \udce9")
        # C0, DEL, C1 — as a character, or as a raw byte of an invalid file name.
        self.assertEqual(shown("\x00\t\x1b\x7f\x9b\udc9b"), "\\x00\\x09\\x1b\\x7f\\x9b\\x9b")


if __name__ == "__main__":
    unittest.main()
