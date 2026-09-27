"""The runtime finds the base through ``cortex.toml`` — ADR-008 §3.6, phase 3.

A synced project holds no spec: its ``cortex.toml`` pins a version, which the runtime reads from
the store, ``{CORTEX_HOME}/versions/{version}``. A project without ``cortex.toml`` resolves as it
always has, from ``{root}/cortex``. A version the store lacks is refused at submission.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.base import base_root_for  # noqa: E402
from cortex_runtime.run import RunRequest, resolve_run  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "host"

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from cortex_runtime.api import create_app  # noqa: E402
    from cortex_runtime.app import WorkspaceConfig  # noqa: E402
    from cortex_runtime.runtime import build_runtime  # noqa: E402
    from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402
    HAVE_FASTAPI = True
except Exception:
    HAVE_FASTAPI = False


class SyncedProjectTestCase(unittest.TestCase):
    """The fixture project, synced: its base moved to a store, ``cortex.toml`` pinning it."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-base-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.project = tmp / "project"
        shutil.copytree(FIXTURE, self.project)
        self.home = tmp / "cortex-home"
        (self.home / "versions").mkdir(parents=True)
        shutil.move(str(self.project / "cortex"), self.home / "versions" / "9.9.9")
        (self.project / "cortex.toml").write_text('version = "9.9.9"\ntheme = "h2g2"\n', encoding="utf-8")
        patcher = mock.patch.dict(os.environ, {"CORTEX_HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, **extra):
        return RunRequest(workspace="host", role="lead-backend", service="svc-a", workflow="code-review", **extra)


class BaseRootTests(SyncedProjectTestCase):
    def test_the_base_is_the_stores_copy_of_the_pinned_version(self):
        self.assertEqual(base_root_for(self.project), self.home / "versions" / "9.9.9")

    def test_a_synced_project_resolves_as_the_fixture_did(self):
        expected = resolve_run(self.request(), FIXTURE, theme="h2g2")
        run = resolve_run(self.request(), self.project, theme="h2g2")
        self.assertEqual(run.system_prompt, expected.system_prompt)
        self.assertEqual(run.workflow, expected.workflow)
        self.assertEqual((run.capabilities, run.layers), (expected.capabilities, expected.layers))
        for token in ("BASE-THEME", "BASE-CHARACTER", "BASE-ROLE", "WORKSPACE-RULE", "SERVICE-RULE", "BASE-CAP"):
            self.assertIn(token, run.system_prompt)

    def test_a_cortex_directory_left_in_the_project_is_not_read(self):
        # The pinned version decides; an old copy — or cortex.local.toml's spec — never does.
        stale = self.project / "cortex" / "agents" / "roles" / "engineering"
        stale.mkdir(parents=True)
        (stale / "lead-backend.md").write_text("# STALE-ROLE\n", encoding="utf-8")
        (self.project / "cortex.local.toml").write_text('spec = "cortex"\n', encoding="utf-8")
        run = resolve_run(self.request(), self.project, theme="h2g2")
        self.assertIn("BASE-ROLE", run.system_prompt)
        self.assertNotIn("STALE-ROLE", run.system_prompt)

    def test_a_version_missing_from_the_store_is_refused_and_named(self):
        (self.project / "cortex.toml").write_text('version = "9.9.8"\ntheme = "h2g2"\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "uses Cortex 9.9.8, which is not in the store"):
            resolve_run(self.request(), self.project, theme="h2g2")

    def test_a_version_that_is_no_version(self):
        for text in ('version = "../../etc"\n', 'version = 1\n', 'theme = "h2g2"\n', 'version = "1.0.0/x"\n', "not toml ="):
            with self.subTest(text=text):
                (self.project / "cortex.toml").write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    base_root_for(self.project)


class WithoutCortexTomlTests(unittest.TestCase):
    def test_the_base_stays_under_the_project(self):
        self.assertIsNone(base_root_for(FIXTURE))

    def test_cortex_home_changes_nothing_for_it(self):
        before = resolve_run(RunRequest(workspace="host", role="lead-backend", service="svc-a"), FIXTURE, theme="h2g2")
        with mock.patch.dict(os.environ, {"CORTEX_HOME": "/nonexistent"}):
            after = resolve_run(RunRequest(workspace="host", role="lead-backend", service="svc-a"), FIXTURE, theme="h2g2")
        self.assertEqual(after.system_prompt, before.system_prompt)


@unittest.skipUnless(HAVE_FASTAPI, "fastapi (+ test client deps) not installed")
class ApiTests(SyncedProjectTestCase):
    def client(self, queue=False):
        runtime = build_runtime({"host": WorkspaceConfig(root=self.project, theme="h2g2")},
                                store=InMemoryStateStore(), model_backend="demo")
        if not queue:
            return TestClient(create_app(runtime))
        job_queue = runtime.build_queue()
        self.addCleanup(job_queue.shutdown)
        return TestClient(create_app(runtime, queue=job_queue))

    def test_a_synced_project_runs(self):
        r = self.client().post("/run", json={"workspace": "host", "role": "support-engineer", "subject": "ACME-7",
                                             "input": {"issue": "ACME-7"}})
        self.assertEqual(r.status_code, 200, r.text)

    def test_a_version_missing_from_the_store_is_a_422_naming_it(self):
        (self.project / "cortex.toml").write_text('version = "9.9.8"\ntheme = "h2g2"\n', encoding="utf-8")
        for queue in (False, True):
            with self.subTest(asynchronous=queue):
                client = self.client(queue)
                for path in ("/run", "/resolve"):
                    r = client.post(path, json={"workspace": "host", "role": "lead-backend", "subject": "ACME-8"})
                    self.assertEqual(r.status_code, 422, r.text)
                    self.assertIn("Cortex 9.9.8", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()
