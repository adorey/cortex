"""Tests for the swappable secret backend — ADR-002 §3.6."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.secret_provider import (  # noqa: E402
    ChainSecretProvider,
    DotenvSecretProvider,
    EnvSecretProvider,
    SecretNotFound,
    parse_dotenv,
)


class ParseDotenvTests(unittest.TestCase):
    def test_parses_keys_comments_quotes_export(self):
        env = parse_dotenv(
            "\n".join([
                "# a comment",
                "",
                "LLM_KEY=sk-123",
                'QUOTED="with spaces"',
                "export EXPORTED=val",
                "noequalsline",
            ])
        )
        self.assertEqual(env["LLM_KEY"], "sk-123")
        self.assertEqual(env["QUOTED"], "with spaces")
        self.assertEqual(env["EXPORTED"], "val")
        self.assertNotIn("noequalsline", env)


class DotenvProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / ".env.local"
        self.tmp.write_text("LLM_KEY=sk-local\nWBTB_LLM_KEY=sk-wbtb\n", encoding="utf-8")

    def test_get_normalizes_name(self):
        p = DotenvSecretProvider(self.tmp)
        self.assertEqual(p.get("llm_key"), "sk-local")          # llm_key → LLM_KEY

    def test_per_tenant_namespace(self):
        p = DotenvSecretProvider(self.tmp, namespace="wbtb")
        self.assertEqual(p.get("llm_key"), "sk-wbtb")           # → WBTB_LLM_KEY

    def test_missing_raises(self):
        with self.assertRaises(SecretNotFound):
            DotenvSecretProvider(self.tmp).get("absent_secret")

    def test_optional_returns_default(self):
        self.assertIsNone(DotenvSecretProvider(self.tmp).get_optional("absent"))


class EnvProviderTests(unittest.TestCase):
    def test_reads_process_env(self):
        os.environ["CORTEX_TEST_LLM_KEY"] = "sk-env"
        try:
            self.assertEqual(EnvSecretProvider(namespace="cortex_test").get("llm_key"), "sk-env")
        finally:
            del os.environ["CORTEX_TEST_LLM_KEY"]


class ChainProviderTests(unittest.TestCase):
    def test_first_hit_wins(self):
        dotenv = Path(tempfile.mkdtemp()) / ".env.local"
        dotenv.write_text("LLM_KEY=from-file\n", encoding="utf-8")
        os.environ["LLM_KEY"] = "from-env"
        try:
            chain = ChainSecretProvider([DotenvSecretProvider(dotenv), EnvSecretProvider()])
            self.assertEqual(chain.get("llm_key"), "from-file")   # file wins over env
        finally:
            del os.environ["LLM_KEY"]

    def test_falls_through_to_env(self):
        empty = Path(tempfile.mkdtemp()) / ".env.local"
        empty.write_text("# nothing\n", encoding="utf-8")
        os.environ["ISSUE_TRACKER_TOKEN"] = "tok"
        try:
            chain = ChainSecretProvider([DotenvSecretProvider(empty), EnvSecretProvider()])
            self.assertEqual(chain.get("issue_tracker_token"), "tok")
        finally:
            del os.environ["ISSUE_TRACKER_TOKEN"]


if __name__ == "__main__":
    unittest.main()
