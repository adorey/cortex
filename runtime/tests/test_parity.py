"""Parity guard: the Python resolver must agree with ``bin/validate-overlays.sh``
on a fixture cascade, so the two implementations cannot drift apart (ADR-002 §3.1).

Agreement, per overlay file:
  • validator ACCEPTS it (✓)            → the resolver STACKS it (overlay ∈ cascade)
  • validator REJECTS it NON_OVERRIDABLE → the resolver IGNORES it (base content only)

The bash script is copied into a temp host layout so its path assumptions
({root}/cortex/bin/…) hold. Skipped cleanly if bash or the script is unavailable.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.resolver import (  # noqa: E402
    MergeSemantic,
    read_resolved,
    resolve_layer,
    semantic_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "host"
VALIDATOR = REPO_ROOT / "bin" / "validate-overlays.sh"

# Lines like "✓ agents/roles/…md" or "✗ svc-a/agents/…md"
_VERDICT = re.compile(r"^\s*([✓✗])\s+(\S+\.md)\s*$")


def _split_overlay_path(rel: str):
    """'agents/roles/x/y.md' → (layer, file, None);  'svc/agents/roles/x.md' → (layer, file, svc)."""
    parts = rel.split("/")
    if parts[0] == "agents":
        return parts[1], "/".join(parts[2:]), None
    return parts[2], "/".join(parts[3:]), parts[0]  # {service}/agents/{layer}/{file}


class ParityTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("bash") is None:
            self.skipTest("bash not available")
        if not VALIDATOR.is_file():
            self.skipTest(f"validator not found: {VALIDATOR}")

        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-parity-"))
        shutil.copytree(FIXTURE, self.tmp, dirs_exist_ok=True)
        (self.tmp / "cortex" / "bin").mkdir(parents=True, exist_ok=True)
        shutil.copy(VALIDATOR, self.tmp / "cortex" / "bin" / VALIDATOR.name)

        proc = subprocess.run(
            ["bash", str(self.tmp / "cortex" / "bin" / VALIDATOR.name)],
            capture_output=True, text=True,
        )
        self.verdicts = {}  # rel_path -> accepted(bool)
        for line in proc.stdout.splitlines():
            m = _VERDICT.match(line)
            if m:
                self.verdicts[m.group(2)] = (m.group(1) == "✓")

    def tearDown(self):
        if getattr(self, "tmp", None):
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_validator_discovered_overlays(self):
        # Sanity: the parsing actually found the fixture overlays (else the test is vacuous).
        self.assertGreaterEqual(len(self.verdicts), 5, f"parsed too few verdicts: {self.verdicts}")

    def test_resolver_agrees_with_validator(self):
        for rel, accepted in self.verdicts.items():
            layer, file, service = _split_overlay_path(rel)
            resolved = ["/".join(p.relative_to(self.tmp).parts)
                        for p in resolve_layer(layer, file, service, self.tmp)]
            with self.subTest(overlay=rel, accepted=accepted):
                if accepted:
                    # Validator accepted the overlay → resolver must stack it onto its base.
                    self.assertIn(rel, resolved, f"{rel}: accepted by validator but not stacked")
                    self.assertGreaterEqual(len(resolved), 2, f"{rel}: overlay present without a base")
                else:
                    # Validator rejected as non-overridable → resolver must use base only.
                    self.assertIs(semantic_for(layer, file), MergeSemantic.NOT_OVERRIDABLE)
                    merged = read_resolved(layer, file, service, self.tmp)
                    self.assertNotIn("WORKSPACE-CHARACTERS", merged,
                                     f"{rel}: rejected overlay leaked into resolved content")


if __name__ == "__main__":
    unittest.main()
