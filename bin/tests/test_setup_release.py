"""bin/setup-release.sh against a fake GitHub: what --check reports, what a run applies, and that a
second run changes nothing (ADR-009 §3.10). The live check is on a throwaway repository."""

import copy
import io
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

BIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BIN))
import setup_release as sr  # noqa: E402


class FakeGh(sr.Gh):
    """One repository's settings, as GitHub's API serves and takes them."""

    def __init__(self, owner_type="Organization", rulesets=None, immutable=False, delete_on_merge=False, branches=("main",)):
        self.owner_type = owner_type
        self.branches = list(branches)
        self.rulesets = {r["id"]: r for r in (rulesets or [])}
        self.immutable = immutable
        self.delete_on_merge = delete_on_merge
        self.writes = []

    def api(self, path, method="GET", body=None):
        if method != "GET":
            self.writes.append((method, path))
        if path == "repos/o/r" and method == "GET":
            return {"owner": {"type": self.owner_type}, "delete_branch_on_merge": self.delete_on_merge}
        if path == "repos/o/r" and method == "PATCH":
            self.delete_on_merge = body["delete_branch_on_merge"]
            return {}
        if path.startswith("repos/o/r/rulesets?"):
            return [{"id": i, "name": r["name"], "source_type": "Repository"} for i, r in self.rulesets.items()]
        if path.startswith("repos/o/r/branches?"):
            return [{"name": b} for b in self.branches] if "page=1" in path else []
        if path.startswith("repos/o/r/rulesets") and method in ("POST", "PUT"):
            # As GitHub does: no merge queue on a pattern.
            if any(r["type"] == "merge_queue" for r in body["rules"]) and any("*" in ref for ref in body["conditions"]["ref_name"]["include"]):
                raise sr.GhError("Invalid rule 'merge_queue': Wildcard ref names are not supported when merge queue is enabled")
        if path == "repos/o/r/rulesets" and method == "POST":
            new = dict(copy.deepcopy(body), id=len(self.rulesets) + 100)
            self.rulesets[new["id"]] = new
            return new
        match = re.fullmatch(r"repos/o/r/rulesets/(\d+)", path)
        if match:
            if method == "PUT":
                self.rulesets[int(match.group(1))] = dict(copy.deepcopy(body), id=int(match.group(1)))
            # GitHub adds parameters of its own to a rule: --check must not take them for drift.
            served = copy.deepcopy(self.rulesets[int(match.group(1))])
            for rule in served.get("rules", []):
                if rule["type"] == "pull_request":
                    rule["parameters"]["required_reviewers"] = []
            return served
        if path == "repos/o/r/immutable-releases":
            if method == "PUT":
                self.immutable = True
                return None
            return {"enabled": self.immutable, "enforced_by_owner": False}
        raise AssertionError((method, path))


def run(gh, *args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = sr.main(["o/r", *args], gh=gh)
    return code, out.getvalue()


class SetupReleaseTests(unittest.TestCase):
    def test_check_reports_every_setting_that_differs_and_changes_nothing(self):
        gh = FakeGh()
        code, out = run(gh, "--check")
        self.assertEqual(code, 1)
        self.assertEqual(gh.writes, [])
        self.assertIn("there is no ruleset named 'release cycle'", out)
        self.assertIn("✗ immutable releases\n    they are off", out)
        self.assertIn("✗ head branches deleted on merge\n    they are kept", out)
        self.assertIn("there is no ruleset named 'release cycle: merge queue'", out)
        self.assertIn("4 setting(s) differ.", out)

    def test_one_run_applies_them_and_a_second_changes_nothing(self):
        gh = FakeGh()
        self.assertEqual(run(gh)[0], 0)
        self.assertEqual([w[0] for w in gh.writes], ["POST", "POST", "PUT", "PATCH"])
        code, out = run(gh, "--check")
        self.assertEqual(code, 0, out)
        self.assertIn("Every setting holds.", out)
        before = list(gh.writes)
        code, out = run(gh)
        self.assertEqual((code, gh.writes), (0, before))
        self.assertIn("Nothing to change.", out)

    def rulesets(self, gh):
        return {r["name"]: r for r in gh.rulesets.values()}

    def test_the_rulesets_an_organisation_gets(self):
        gh = FakeGh(branches=["main", "1.x", "release/1.4.0", "feature.x"])
        run(gh)
        ruleset = self.rulesets(gh)["release cycle"]
        self.assertEqual(ruleset["enforcement"], "active")
        self.assertEqual(ruleset["bypass_actors"], [])
        self.assertEqual(ruleset["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH", "refs/heads/*.x"])
        rules = {r["type"]: r.get("parameters", {}) for r in ruleset["rules"]}
        self.assertEqual(sorted(rules), ["deletion", "non_fast_forward", "pull_request", "required_status_checks"])
        self.assertEqual(rules["pull_request"]["allowed_merge_methods"], ["merge"])
        self.assertTrue(rules["required_status_checks"]["strict_required_status_checks_policy"])
        queue = self.rulesets(gh)["release cycle: merge queue"]
        # Named exactly: GitHub refuses a merge queue on a pattern. `feature.x` is no line.
        self.assertEqual(queue["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH", "refs/heads/1.x"])
        self.assertEqual(queue["bypass_actors"], [])
        params = queue["rules"][0]["parameters"]
        self.assertEqual((queue["rules"][0]["type"], params["merge_method"], params["max_entries_to_merge"]), ("merge_queue", "MERGE", 1))

    def test_a_new_line_is_drift_until_the_script_runs_again(self):
        gh = FakeGh()
        run(gh)
        gh.branches.append("2.x")
        code, out = run(gh, "--check")
        self.assertEqual(code, 1)
        self.assertIn("✗ the ruleset 'release cycle: merge queue', on the default branch, 2.x", out)
        self.assertIn("it applies to ['~DEFAULT_BRANCH'], and should apply to ['refs/heads/2.x', '~DEFAULT_BRANCH']", out)
        self.assertEqual(run(gh)[0], 0)
        self.assertEqual(run(gh, "--check")[0], 0)

    def test_a_personal_repository_gets_no_merge_queue(self):
        gh = FakeGh(owner_type="User")
        code, out = run(gh)
        self.assertIn("No merge queue: GitHub offers it to repositories of organisations.", out)
        self.assertEqual(list(self.rulesets(gh)), ["release cycle"])
        self.assertEqual(run(gh, "--check")[0], 0)

    def test_no_required_check_is_a_matrix_job(self):
        for name in sr.DEFAULT_CHECKS:
            with self.subTest(check=name):
                self.assertNotIn("${{", name)
                self.assertNotIn("(", name)

    def test_the_required_checks_are_job_names_of_this_repository(self):
        workflows = BIN.parent / ".github" / "workflows"
        names = set()
        for path in workflows.glob("*.yml"):
            names |= set(re.findall(r"(?m)^    name: (.+?)\s*$", path.read_text(encoding="utf-8")))
        for check in sr.DEFAULT_CHECKS:
            with self.subTest(check=check):
                self.assertIn(check, names)

    def test_each_required_check_of_several_jobs_fails_when_one_of_them_does(self):
        # A summary runs whatever happened, needs every job a pull request runs — a job of a tag's
        # push only is none — and fails on a failure or a cancellation (§3.10). Read as text: the
        # runner's Python has no YAML parser.
        summaries = set()
        for path in sorted((BIN.parent / ".github" / "workflows").glob("*.yml")):
            block = path.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
            parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):\s*\n", block)
            jobs = dict(zip(parts[1::2], parts[2::2]))

            def key(job, name):
                match = re.search(rf"(?m)^    {name}: (.+?)\s*$", job)
                return match.group(1) if match else ""

            for job_id, job in jobs.items():
                if key(job, "name") not in sr.DEFAULT_CHECKS or len(jobs) == 1:
                    continue
                summaries.add(key(job, "name"))
                others = {other for other, text in jobs.items()
                          if other != job_id and "github.event_name == 'push'" not in key(text, "if")}
                with self.subTest(workflow=path.name, check=key(job, "name")):
                    self.assertEqual(key(job, "if"), "always()")
                    self.assertEqual(set(re.findall(r"[A-Za-z0-9_-]+", key(job, "needs"))), others)
                    self.assertRegex(job, r"(?m)^          \[ \"\$\{\{ contains\(needs\.\*\.result, 'failure'\) \|\| "
                                          r"contains\(needs\.\*\.result, 'cancelled'\) \}\}\" = false \]$")
        self.assertEqual(summaries, {"builds", "cli tests", "core tests", "repo checks", "runtime tests"})

    def test_a_disabled_or_loosened_ruleset_is_drift(self):
        gh = FakeGh()
        run(gh)
        ruleset = self.rulesets(gh)["release cycle"]
        ruleset["enforcement"] = "disabled"
        ruleset["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
        for rule in ruleset["rules"]:
            if rule["type"] == "pull_request":
                rule["parameters"]["allowed_merge_methods"] = ["merge", "squash"]
            if rule["type"] == "required_status_checks":
                rule["parameters"]["required_status_checks"] = rule["parameters"]["required_status_checks"][1:] + [
                    {"context": "build (linux-x86_64)", "integration_id": 15368}]
        ruleset["rules"].append({"type": "required_signatures"})
        code, out = run(gh, "--check")
        self.assertEqual(code, 1)
        for expected in ("it is disabled, not active",
                         "it lets 1 actor(s) bypass it, and should let nobody",
                         'its pull_request rule has allowed_merge_methods = ["merge", "squash"], and should have ["merge"]',
                         "missing ['actions tests (15368)'], not required here ['build (linux-x86_64) (15368)']",
                         "it has a required_signatures rule, which the cycle does not set"):
            with self.subTest(expected=expected):
                self.assertIn(expected, out)
        self.assertEqual(run(gh)[0], 0)
        self.assertEqual(run(gh, "--check")[0], 0)

    def test_another_repositorys_checks(self):
        gh = FakeGh()
        run(gh, "--require", "ci", "--require", "lint")
        rules = {r["type"]: r.get("parameters", {}) for r in self.rulesets(gh)["release cycle"]["rules"]}
        self.assertEqual([c["context"] for c in rules["required_status_checks"]["required_status_checks"]], ["ci", "lint"])

    def test_an_api_error_stops_with_its_message(self):
        class Refusing(FakeGh):
            def api(self, path, method="GET", body=None):
                raise sr.GhError(f"{method} {path}: HTTP 404")
        err = io.StringIO()
        saved, sys.stderr = sys.stderr, err
        try:
            self.assertEqual(run(Refusing())[0], 2)
        finally:
            sys.stderr = saved
        self.assertIn("HTTP 404", err.getvalue())


if __name__ == "__main__":
    unittest.main()
