"""Cascade resolution, merge semantics and lookups — ADR-001 §3.1/§3.2, ADR-007.

Runnable with zero install:  cd core && python3 -m unittest discover -s tests -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make cortex_core importable

from cortex_core.resolver import (  # noqa: E402
    MergeSemantic,
    character_for_role,
    default_base_root,
    find_role_relpath,
    find_workflow_relpath,
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
        roots = [p.relative_to(ROOT).parts[0] for p in paths]
        self.assertEqual(roots, ["cortex", "agents", "svc-a"])  # base → workspace → service

    def test_service_ignored_when_none(self):
        paths = resolve_layer("roles", "engineering/lead-backend.md", None, ROOT)
        self.assertFalse(any(p.relative_to(ROOT).parts[0] == "svc-a" for p in paths))

    def test_missing_returns_empty(self):
        self.assertEqual(resolve_layer("roles", "engineering/ghost.md", "svc-a", ROOT), [])


class BaseRootTests(unittest.TestCase):
    """ADR-007 §3.1 — the base is located by ``base_root``; leaving it out changes nothing."""

    CASES = [
        ("roles", "engineering/lead-backend.md", "svc-a"),
        ("roles", "engineering/lead-backend.md", None),
        ("personalities", "h2g2/characters.md", None),
        ("workflows", "engineering/code-review.md", None),
        ("capabilities", "languages/php.md", "svc-a"),
    ]

    def test_default_is_the_cortex_checkout(self):
        self.assertEqual(default_base_root(ROOT), ROOT / "cortex")

    def test_omitted_equals_explicit_default(self):
        for layer, file, service in self.CASES:
            with self.subTest(layer=layer, file=file, service=service):
                self.assertEqual(
                    resolve_layer(layer, file, service, ROOT),
                    resolve_layer(layer, file, service, ROOT, base_root=ROOT / "cortex"),
                )
                self.assertEqual(
                    read_resolved(layer, file, service, ROOT),
                    read_resolved(layer, file, service, ROOT, base_root=ROOT / "cortex"),
                )

    def test_base_outside_the_project_tree(self):
        # A base installed elsewhere — what ADR-008 will point base_root at.
        tmp = Path(tempfile.mkdtemp(prefix="cortex-base-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        install = tmp / "install"
        shutil.copytree(ROOT / "cortex", install)
        project = tmp / "project"
        shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns("cortex"))

        paths = resolve_layer("roles", "engineering/lead-backend.md", "svc-a", project, base_root=install)
        self.assertEqual(paths[0], install / "agents" / "roles" / "engineering" / "lead-backend.md")
        self.assertEqual(len(paths), 3)
        self.assertEqual(find_role_relpath("lead-backend", project, base_root=install), "engineering/lead-backend.md")
        self.assertEqual(find_workflow_relpath("code-review", project, base_root=install), "engineering/code-review.md")
        self.assertEqual(character_for_role("lead-backend", "h2g2", project, base_root=install), "h2g2/Hactar.md")
        # and without base_root the same project has no base at all
        self.assertIsNone(find_role_relpath("lead-backend", project))


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


class FindTests(unittest.TestCase):
    def test_finds_role_category(self):
        self.assertEqual(find_role_relpath("lead-backend", ROOT), "engineering/lead-backend.md")

    def test_unknown_role_none(self):
        self.assertIsNone(find_role_relpath("ghost", ROOT))

    def test_finds_workflow_category(self):
        self.assertEqual(find_workflow_relpath("code-review", ROOT), "engineering/code-review.md")


if __name__ == "__main__":
    unittest.main()
