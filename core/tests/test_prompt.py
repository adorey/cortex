"""Prompt assembly — ADR-007: moved from the runtime byte for byte, then parameterised."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_core.prompt import build_system_prompt, layers_for  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = FIXTURES / "host"

# Captured from the runtime's build_system_prompt before the move: name → (role, service, theme, capabilities).
GOLDEN = {
    "lead-backend": ("lead-backend", None, None, None),
    "lead-backend.svc-a": ("lead-backend", "svc-a", None, None),
    "lead-backend.h2g2": ("lead-backend", None, "h2g2", None),
    "lead-backend.svc-a.h2g2.caps": ("lead-backend", "svc-a", "h2g2", ["languages/php.md", "languages/typescript.md"]),
    "ghost.h2g2": ("ghost", None, "h2g2", None),
}


class GoldenPromptTests(unittest.TestCase):
    def test_byte_identical_to_the_runtime_before_the_move(self):
        for name, (role, service, theme, caps) in GOLDEN.items():
            expected = (FIXTURES / "golden" / f"prompt.{name}.txt").read_text(encoding="utf-8")
            with self.subTest(case=name):
                self.assertEqual(build_system_prompt(role, service, theme, ROOT, caps), expected)

    def test_omitted_base_root_equals_explicit_default(self):
        for name, (role, service, theme, caps) in GOLDEN.items():
            with self.subTest(case=name):
                self.assertEqual(
                    build_system_prompt(role, service, theme, ROOT, caps),
                    build_system_prompt(role, service, theme, ROOT, caps, base_root=ROOT / "cortex"),
                )


class LayersForTests(unittest.TestCase):
    def test_personality_then_role(self):
        self.assertEqual(
            layers_for("lead-backend", "h2g2", ROOT),
            [
                ("personalities", "h2g2/theme.md"),
                ("personalities", "h2g2/Hactar.md"),
                ("roles", "engineering/lead-backend.md"),
            ],
        )

    def test_no_theme(self):
        self.assertEqual(layers_for("lead-backend", None, ROOT), [("roles", "engineering/lead-backend.md")])

    def test_theme_none_string(self):
        self.assertEqual(layers_for("lead-backend", "none", ROOT), [("roles", "engineering/lead-backend.md")])

    def test_unknown_role_keeps_theme_only(self):
        self.assertEqual(layers_for("ghost", "h2g2", ROOT), [("personalities", "h2g2/theme.md")])


class BuildSystemPromptTests(unittest.TestCase):
    def test_full_assembly_ordered(self):
        prompt = build_system_prompt("lead-backend", "svc-a", "h2g2", ROOT, capabilities=["languages/php.md"])
        order = ["BASE-THEME", "WORKSPACE-THEME", "BASE-CHARACTER",
                 "BASE-ROLE", "WORKSPACE-RULE", "SERVICE-RULE",
                 "BASE-CAP", "SERVICE-CAP"]
        positions = [prompt.index(tok) for tok in order]
        self.assertEqual(positions, sorted(positions), f"out of order: {positions}")
        self.assertNotIn("Marvin", prompt)  # characters.md remap never leaks in

    def test_layer_separator_present(self):
        self.assertIn("\n\n---\n\n", build_system_prompt("lead-backend", None, "h2g2", ROOT))

    def test_no_theme_no_personality(self):
        prompt = build_system_prompt("lead-backend", None, None, ROOT)
        self.assertIn("BASE-ROLE", prompt)
        self.assertNotIn("BASE-THEME", prompt)

    def test_capabilities_default_empty(self):
        self.assertNotIn("BASE-CAP", build_system_prompt("lead-backend", None, None, ROOT))


if __name__ == "__main__":
    unittest.main()
