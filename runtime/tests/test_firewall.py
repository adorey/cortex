"""The architectural firewall (ADR-002 §2): the runtime consumes the spec; the spec
never depends on the runtime.

This guard fails if any spec Markdown under ``agents/`` references the engine. The
firewall is enforced mechanically here, not by a repo boundary — we chose a monorepo.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = REPO_ROOT / "agents"

# Unambiguous engine references that have no business in portable, host-agnostic spec
# Markdown. (Mentioning a web framework in a capability doc is fine; importing the
# runtime or naming its internal symbols / API contract is not.)
FORBIDDEN_TOKENS = [
    "cortex_runtime",
    "from cortex_runtime",
    "import cortex_runtime",
    "resolve_layer(",
    "build_system_prompt(",
    "POST /run",
]


class FirewallTests(unittest.TestCase):
    def test_spec_does_not_reference_runtime(self):
        self.assertTrue(SPEC_DIR.is_dir(), f"spec dir not found: {SPEC_DIR}")
        offenders = []
        for md in SPEC_DIR.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            for token in FORBIDDEN_TOKENS:
                if token in text:
                    offenders.append(f"{md.relative_to(REPO_ROOT)} :: '{token}'")
        self.assertEqual(
            offenders, [],
            "Spec Markdown must not depend on the runtime (ADR-002 firewall):\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
