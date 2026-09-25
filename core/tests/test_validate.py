"""The validator's checks, tier by tier, against the verdicts captured from the script."""

import io
import json
import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_core.validate import Abort, Colors, Report, check_overlay, echo_e_line, validate  # noqa: E402
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
        try:
            for path in overlays:
                check_overlay(str(path), str(project), str(project / "cortex"), report)
        except Abort:
            return None, out.getvalue().split("\n")[:-1]
        return report, out.getvalue().split("\n")[:-1]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class VerdictTestCase(unittest.TestCase):
    def assert_case(self, case):
        report, lines = core_verdicts(case)
        expected = captured_verdicts(case)
        if report is None:  # the script aborted before any verdict
            self.assertEqual(EXPECTED[case]["default"]["code"], 1)
        self.assertEqual(lines, expected)


class Tier1Tests(VerdictTestCase):
    def test_every_tier_1_case_gets_its_captured_verdicts(self):
        for case in TIER_1:
            with self.subTest(case=case):
                self.assert_case(case)


TIER_2 = ["non-overridable", "sections-untagged", "scope-service-at-root", "scope-workspace-in-service",
          # depth 3 — a service overlay straight under its layer directory: the script does not warn
          "scope-workspace-in-service-shallow", "unknown-layer"]


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


class EchoTests(unittest.TestCase):
    def test_bash_echo_e_escapes(self):
        self.assertEqual(echo_e_line("a\\tb"), "a\tb\n")
        self.assertEqual(echo_e_line("x\\cy"), "x")            # \c cuts the output and its newline
        self.assertEqual(echo_e_line("p\\qz"), "p\\qz\n")      # an unknown escape stays as it is
        self.assertEqual(echo_e_line("\\x41\\0102"), "AB\n")

    def test_incomplete_escapes_are_printed_as_they_are(self):
        # What Bash prints — and a Windows-style Base: path, \users included, used to crash the port.
        self.assertEqual(echo_e_line("a\\xyz"), "a\\xyz\n")
        self.assertEqual(echo_e_line("\\users\\Ux"), "\\users\\Ux\n")

    def test_escapes_write_the_bytes_bash_writes(self):
        # Measured with Bash under C.UTF-8. A byte that is not UTF-8 is carried as surrogateescape,
        # which the output stream writes back as that very byte.
        raw = lambda *bs: "".join(chr(0xDC00 + b) for b in bs)  # noqa: E731
        self.assertEqual(echo_e_line("\\xe9\\0351"), raw(0xE9, 0xE9) + "\n")
        self.assertEqual(echo_e_line("\\u00e9"), "\u00e9\n")
        self.assertEqual(echo_e_line("\\uD800"), raw(0xED, 0xA0, 0x80) + "\n")
        self.assertEqual(echo_e_line("\\U00110000"), raw(0xF4, 0x90, 0x80, 0x80) + "\n")
        self.assertEqual(echo_e_line("\\U7FFFFFFF"), raw(0xFD, 0xBF, 0xBF, 0xBF, 0xBF, 0xBF) + "\n")
        self.assertEqual(echo_e_line("p\\UFFFFFFFFq"), "pq\n")


if __name__ == "__main__":
    unittest.main()
