"""The nightly re-run of the gate, against a fake GitHub."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nightly"))
import nightly  # noqa: E402
from github import GitHubError  # noqa: E402


class FakeGitHub:
    def __init__(self, pulls, runs, refuse=()):
        self.pulls, self.runs, self.refuse = pulls, runs, set(refuse)
        self.reran = []

    def repo(self, suffix=""):
        return f"/repos/o/r{suffix}"

    def get(self, path):
        if path == "/repos/o/r":
            return {"default_branch": "main"}
        if "/actions/workflows/release-gate.yml/runs" in path:
            sha = path.split("head_sha=")[1].split("&")[0]
            return {"workflow_runs": self.runs.get(sha, [])}
        raise AssertionError(path)

    def paginate(self, path):
        assert path == "/repos/o/r/pulls?state=open", path
        return iter(self.pulls)

    def request(self, method, path, **_):
        run = int(path.split("/runs/")[1].split("/")[0])
        if run in self.refuse:
            raise GitHubError(403, "Unable to re-run this workflow run because it was created over a month ago")
        self.reran.append((method, run))


def pull(number, base, sha):
    return {"number": number, "base": {"ref": base}, "head": {"sha": sha}}


def run(run_id, created, status="completed", conclusion="success"):
    return {"id": run_id, "created_at": created, "status": status, "conclusion": conclusion}


class NightlyTests(unittest.TestCase):
    def test_the_gate_of_each_pull_request_into_main_or_a_line_runs_again(self):
        github = FakeGitHub(
            [pull(1, "main", "a" * 40), pull(2, "1.x", "b" * 40), pull(3, "release/1.4.0", "c" * 40),
             pull(4, "adr-009/phase-2", "d" * 40)],
            {"a" * 40: [run(10, "2026-11-01T10:00:00Z"), run(11, "2026-11-02T10:00:00Z")],
             "b" * 40: [run(20, "2026-11-02T09:00:00Z", conclusion="failure")]})
        outcomes = nightly.again(github, "release-gate.yml")
        self.assertEqual(github.reran, [("POST", 11), ("POST", 20)])
        self.assertEqual([(o.number, o.rerun) for o in outcomes], [(1, True), (2, True)])
        self.assertIn("which was success", outcomes[0].what)

    def test_a_gate_that_never_ran_or_is_running_is_left_alone(self):
        github = FakeGitHub([pull(1, "main", "a" * 40), pull(2, "main", "b" * 40)],
                            {"b" * 40: [run(20, "2026-11-02T09:00:00Z", status="in_progress", conclusion=None)]})
        outcomes = nightly.again(github, "release-gate.yml")
        self.assertEqual(github.reran, [])
        self.assertEqual([o.what for o in outcomes], [f"no run of release-gate.yml at {'a' * 7}: left alone",
                                                      "its gate is in_progress: left alone"])

    def test_a_run_github_refuses_to_re_run_is_reported(self):
        github = FakeGitHub([pull(1, "main", "a" * 40)], {"a" * 40: [run(10, "2026-09-01T10:00:00Z")]}, refuse=[10])
        outcome = nightly.again(github, "release-gate.yml")[0]
        self.assertFalse(outcome.rerun)
        self.assertTrue(outcome.what.startswith("could not re-run run 10: HTTP 403"))

    def test_what_it_targets(self):
        for base, expected in (("main", True), ("1.x", True), ("10.x", True), ("release/1.x", False),
                               ("develop", False), ("1.2.x", False)):
            with self.subTest(base=base):
                self.assertIs(nightly.targets(base, "main"), expected)


if __name__ == "__main__":
    unittest.main()
