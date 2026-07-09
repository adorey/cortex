"""Unit tests for the cascade resolver — ADR-001 §3.1/§3.2 (ADR-002 §3.1).

Runnable with zero install:  python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make cortex_runtime importable

from cortex_runtime.resolver import (  # noqa: E402
    MergeSemantic,
    build_system_prompt,
    character_for_role,
    find_role_relpath,
    layers_for,
    read_resolved,
    resolve_layer,
    semantic_for,
)

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"


class ResolveLayerTests(unittest.TestCase):
    def test_base_only(self):
        paths = resolve_layer("personalities", "h2g2/Hactar.md", None, ROOT)
        self.assertEqual(len(paths), 1)
        self.assertTrue(str(paths[0]).endswith("cortex/agents/personalities/h2g2/Hactar.md"))

    def test_base_plus_workspace(self):
        paths = resolve_layer("roles", "engineering/lead-backend.md", None, ROOT)
        self.assertEqual(len(paths), 2)
        # ordered base → workspace (compare RELATIVE to ROOT — the repo itself is named "cortex")
        self.assertEqual(paths[0].relative_to(ROOT).parts[0], "cortex")
        self.assertEqual(paths[1].relative_to(ROOT).parts[0], "agents")

    def test_full_cascade_ordered(self):
        paths = resolve_layer("roles", "engineering/lead-backend.md", "svc-a", ROOT)
        self.assertEqual(len(paths), 3)
        roots = [p.relative_to(ROOT).parts[0] for p in paths]
        self.assertEqual(roots, ["cortex", "agents", "svc-a"])  # base → workspace → service

    def test_service_ignored_when_none(self):
        paths = resolve_layer("roles", "engineering/lead-backend.md", None, ROOT)
        self.assertFalse(any(p.relative_to(ROOT).parts[0] == "svc-a" for p in paths))

    def test_missing_returns_empty(self):
        self.assertEqual(resolve_layer("roles", "engineering/ghost.md", "svc-a", ROOT), [])


class SemanticTests(unittest.TestCase):
    def test_workflows_replacement(self):
        self.assertIs(semantic_for("workflows", "engineering/code-review.md"), MergeSemantic.REPLACEMENT)

    def test_roles_additive(self):
        self.assertIs(semantic_for("roles", "engineering/lead-backend.md"), MergeSemantic.ADDITIVE)

    def test_capabilities_additive(self):
        self.assertIs(semantic_for("capabilities", "languages/php.md"), MergeSemantic.ADDITIVE)

    def test_theme_additive(self):
        self.assertIs(semantic_for("personalities", "h2g2/theme.md"), MergeSemantic.ADDITIVE)

    def test_character_additive(self):
        self.assertIs(semantic_for("personalities", "h2g2/Hactar.md"), MergeSemantic.ADDITIVE)

    def test_characters_not_overridable(self):
        self.assertIs(semantic_for("personalities", "h2g2/characters.md"), MergeSemantic.NOT_OVERRIDABLE)


class ReadResolvedTests(unittest.TestCase):
    def test_additive_full_cascade_in_order(self):
        merged = read_resolved("roles", "engineering/lead-backend.md", "svc-a", ROOT)
        for token in ("BASE-RULE", "WORKSPACE-RULE", "SERVICE-RULE"):
            self.assertIn(token, merged)
        self.assertLess(merged.index("BASE-RULE"), merged.index("WORKSPACE-RULE"))
        self.assertLess(merged.index("WORKSPACE-RULE"), merged.index("SERVICE-RULE"))

    def test_additive_without_service(self):
        merged = read_resolved("roles", "engineering/lead-backend.md", None, ROOT)
        self.assertIn("WORKSPACE-RULE", merged)
        self.assertNotIn("SERVICE-RULE", merged)

    def test_replacement_most_specific_wins(self):
        merged = read_resolved("workflows", "engineering/code-review.md", None, ROOT)
        self.assertIn("WORKSPACE-WORKFLOW", merged)
        self.assertNotIn("BASE-WORKFLOW", merged)  # replacement: base is discarded entirely

    def test_not_overridable_uses_base_only(self):
        merged = read_resolved("personalities", "h2g2/characters.md", None, ROOT)
        self.assertIn("Hactar", merged)
        self.assertNotIn("Marvin", merged)             # overlay remap ignored
        self.assertNotIn("WORKSPACE-CHARACTERS", merged)

    def test_missing_returns_empty_string(self):
        self.assertEqual(read_resolved("roles", "engineering/ghost.md", "svc-a", ROOT), "")


class CharacterForRoleTests(unittest.TestCase):
    def test_lead_backend_maps_to_hactar(self):
        self.assertEqual(character_for_role("lead-backend", "h2g2", ROOT), "h2g2/Hactar.md")

    def test_prompt_manager_maps_to_oolon(self):
        self.assertEqual(character_for_role("prompt-manager", "h2g2", ROOT), "h2g2/Oolon-Colluphid.md")

    def test_unknown_role_returns_none(self):
        self.assertIsNone(character_for_role("ghost", "h2g2", ROOT))

    def test_overlay_remap_is_ignored(self):
        # workspace overlay tries to remap lead-backend → Marvin; characters.md is not overridable.
        self.assertEqual(character_for_role("lead-backend", "h2g2", ROOT), "h2g2/Hactar.md")


class FindRoleTests(unittest.TestCase):
    def test_finds_category(self):
        self.assertEqual(find_role_relpath("lead-backend", ROOT), "engineering/lead-backend.md")

    def test_unknown_role_none(self):
        self.assertIsNone(find_role_relpath("ghost", ROOT))


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
        prompt = build_system_prompt(
            "lead-backend", "svc-a", "h2g2", ROOT, capabilities=["languages/php.md"]
        )
        order = ["BASE-THEME", "WORKSPACE-THEME", "BASE-CHARACTER",
                 "BASE-ROLE", "WORKSPACE-RULE", "SERVICE-RULE",
                 "BASE-CAP", "SERVICE-CAP"]
        positions = [prompt.index(tok) for tok in order]
        self.assertEqual(positions, sorted(positions), f"out of order: {positions}")
        self.assertNotIn("Marvin", prompt)  # characters.md remap never leaks in

    def test_layer_separator_present(self):
        prompt = build_system_prompt("lead-backend", None, "h2g2", ROOT)
        self.assertIn("\n\n---\n\n", prompt)

    def test_no_theme_no_personality(self):
        prompt = build_system_prompt("lead-backend", None, None, ROOT)
        self.assertIn("BASE-ROLE", prompt)
        self.assertNotIn("BASE-THEME", prompt)

    def test_capabilities_default_empty(self):
        prompt = build_system_prompt("lead-backend", None, None, ROOT)
        self.assertNotIn("BASE-CAP", prompt)


if __name__ == "__main__":
    unittest.main()
