"""The container sees the store's versions, and nothing else of it — ADR-008 §3.6.

``~/.cortex`` also holds the binary and, from the machine tier of the configuration (ADR-008 §7),
a ``config.toml`` with this machine's settings: none of it is the runtime's to read.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"


def compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class StoreMountTests(unittest.TestCase):
    def test_the_whole_store_is_never_mounted(self):
        text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn(":/cortex-home:", text)
        self.assertIn("source: ${CORTEX_STORE_PATH:-./no-store}/versions", text)

    def test_the_empty_store_has_its_versions(self):
        self.assertTrue((DEPLOY / "no-store" / "versions").is_dir())

    @unittest.skipUnless(compose_available(), "docker compose not installed")
    def test_compose_mounts_only_the_versions_read_only(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-deploy-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        deploy = tmp / "deploy"
        shutil.copytree(DEPLOY, deploy)
        shutil.copy(deploy / ".env.example", deploy / ".env")
        env = {**os.environ, "CORTEX_PROJECT_PATH": str(tmp), "CORTEX_STORE_PATH": str(tmp / "home")}
        proc = subprocess.run(["docker", "compose", "-f", str(deploy / "compose.yaml"), "config", "--format", "json"],
                              capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        volumes = json.loads(proc.stdout)["services"]["cortex-runtime"]["volumes"]
        store = [v for v in volumes if v["target"].startswith("/cortex-home")]
        self.assertEqual(len(store), 1, store)
        self.assertEqual(store[0]["target"], "/cortex-home/versions")
        self.assertEqual(Path(store[0]["source"]), tmp / "home" / "versions")
        self.assertTrue(store[0]["read_only"])
        self.assertFalse(store[0].get("bind", {}).get("create_host_path", False))


if __name__ == "__main__":
    unittest.main()
