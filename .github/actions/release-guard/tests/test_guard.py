"""The guard, against a fake GitHub (ADR-009 §3.5): what passes, what fails and opens one issue,
and the one thing it repairs, `latest`."""

import copy
import hashlib
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guard  # noqa: E402
from github import GitHubError  # noqa: E402

COMMIT = "c" * 40
SIX = ["SHA256SUMS", "cortex-linux-aarch64.tar.gz", "cortex-linux-x86_64.tar.gz", "cortex-macos-arm64.tar.gz",
       "cortex-spec.tar.gz", "cortex-windows-x86_64.zip"]
SIGNER = "o/r/.github/workflows/release.yml"


def assets(drop=(), corrupt=()):
    files = {name: name.encode() * 7 for name in SIX if name != "SHA256SUMS"}
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    for name in corrupt:
        files[name] = b"replaced"
    files["SHA256SUMS"] = sums.encode()
    return {name: data for name, data in files.items() if name not in drop}


class FakeGitHub:
    repository = "o/r"

    def __init__(self, releases, latest, tags=None):
        self.releases_ = releases
        self.latest = latest
        self.tags = tags or {r["tag_name"]: COMMIT for r in releases}
        self.issues = []
        self.patched = []

    def repo(self, suffix=""):
        return f"/repos/o/r{suffix}"

    def releases(self):
        return copy.deepcopy(self.releases_)

    def download(self, url):
        tag, name = url.split("/")[-2:]
        return next(r for r in self.releases_ if r["tag_name"] == tag)["files"][name]

    def get(self, path):
        if path == "/repos/o/r/releases/latest":
            if self.latest is None:
                raise GitHubError(404, "no latest")
            return {"tag_name": self.latest}
        if path.startswith("/repos/o/r/git/ref/tags/"):
            tag = path.rsplit("/", 1)[1]
            if tag not in self.tags:
                raise GitHubError(404, "no such ref")
            return {"object": {"type": "commit", "sha": self.tags[tag]}}
        raise AssertionError(path)

    def paginate(self, path):
        assert path.startswith("/repos/o/r/issues?state=open&labels="), path
        return iter(self.issues)

    def request(self, method, path, body=None, **_):
        if method == "PATCH":
            rid = int(path.rsplit("/", 1)[1])
            self.patched.append((rid, body))
            self.latest = next(r["tag_name"] for r in self.releases_ if r["id"] == rid)
            return {}
        if method == "POST" and path == "/repos/o/r/issues":
            issue = dict(body, html_url=f"https://github.com/o/r/issues/{len(self.issues) + 1}")
            self.issues.append(issue)
            return issue
        raise AssertionError((method, path))


def release(tag, rid, files=None, immutable=True, prerelease=None, draft=False):
    files = assets() if files is None else files
    return {"id": rid, "tag_name": tag, "draft": draft, "prerelease": "-" in tag if prerelease is None else prerelease,
            "immutable": immutable, "html_url": f"https://github.com/o/r/releases/tag/{tag}", "files": files,
            "assets": [{"name": n, "url": f"https://api/{tag}/{n}"} for n in sorted(files)]}


def verify_names(commit):
    """A verifier that passes the assets whose provenance names ``commit``."""
    return lambda path, repo, wanted, signer: None if wanted == commit and signer == SIGNER else "no attestation matches"


def run(github, tag, verify=None):
    out = io.StringIO()
    with redirect_stdout(out):
        code = guard.main(["--tag", tag, "--expected", "\n".join(SIX), "--signer-workflow", SIGNER],
                          github=github, verify=verify or verify_names(COMMIT))
    return code, out.getvalue()


class PassingTests(unittest.TestCase):
    def test_a_release_drafted_by_the_cycle_passes(self):
        github = FakeGitHub([release("1.4.0", 1), release("1.3.0", 2)], latest="1.4.0")
        code, out = run(github, "1.4.0")
        self.assertEqual(code, 0, out)
        self.assertIn("1.4.0 passes its guard.", out)
        for line in ("the tag 1.4.0 is a version", "the 6 assets expected are there", "SHA256SUMS matches the assets",
                     f"the provenance of every asset names {COMMIT[:12]}, signed by {SIGNER}",
                     "the release is immutable", "latest is 1.4.0, the highest version"):
            self.assertIn(f"✓ {line}", out)
        self.assertEqual((github.issues, github.patched), ([], []))

    def test_a_pre_release_passes_and_leaves_latest_alone(self):
        github = FakeGitHub([release("1.4.0-rc.1", 1), release("1.3.0", 2)], latest="1.3.0")
        self.assertEqual(run(github, "1.4.0-rc.1")[0], 0)
        self.assertEqual(github.latest, "1.3.0")


class FailingTests(unittest.TestCase):
    def assert_fails(self, github, tag, expected, verify=None):
        code, out = run(github, tag, verify)
        self.assertEqual(code, 1, out)
        self.assertIn(f"✗ {expected}", out)
        self.assertEqual(len(github.issues), 1)
        issue = github.issues[0]
        self.assertEqual((issue["title"], issue["labels"]), (f"Release {tag} failed its guard", ["type:infra"]))
        self.assertIn(expected, issue["body"])
        self.assertIn("It cannot be repaired.", issue["body"])
        self.assertIn(f"{tag} can never be used again", issue["body"])
        return out

    def test_a_missing_asset(self):
        self.assert_fails(FakeGitHub([release("1.4.0", 1, assets(drop=["cortex-macos-arm64.tar.gz"]))], "1.4.0"),
                          "1.4.0", "assets missing: cortex-macos-arm64.tar.gz")

    def test_a_release_made_by_hand_has_no_asset_at_all(self):
        out = self.assert_fails(FakeGitHub([release("1.4.0", 1, {})], "1.4.0"), "1.4.0", "assets missing: SHA256SUMS")
        self.assertIn("✗ there is no SHA256SUMS to check the assets against", out)

    def test_sha256sums_that_does_not_match(self):
        self.assert_fails(FakeGitHub([release("1.4.0", 1, assets(corrupt=["cortex-spec.tar.gz"]))], "1.4.0"),
                          "1.4.0", "SHA256SUMS does not match: cortex-spec.tar.gz")

    def test_a_tag_on_another_commit_than_the_provenance_names(self):
        github = FakeGitHub([release("1.4.0", 1)], "1.4.0", tags={"1.4.0": "d" * 40})
        self.assert_fails(github, "1.4.0", f"the provenance does not name the tag's commit {'d' * 12}")

    def test_a_mutable_release(self):
        self.assert_fails(FakeGitHub([release("1.4.0", 1, immutable=False)], "1.4.0"), "1.4.0",
                          "the release is mutable: its assets could still be replaced")

    def test_a_tag_that_is_no_version(self):
        self.assert_fails(FakeGitHub([release("nightly", 1)], None), "nightly", "the tag 'nightly' is no version")

    def test_one_issue_per_release(self):
        github = FakeGitHub([release("1.4.0", 1, immutable=False)], "1.4.0")
        run(github, "1.4.0")
        run(github, "1.4.0")
        self.assertEqual(len(github.issues), 1)


class LatestTests(unittest.TestCase):
    def test_latest_on_an_older_line_moves_back_to_the_highest(self):
        # 1.5.1 of the 1.x line published with "Set as the latest release" ticked.
        github = FakeGitHub([release("1.5.1", 1), release("2.0.0", 2)], latest="1.5.1")
        code, out = run(github, "1.5.1")
        self.assertEqual(code, 0, out)
        self.assertEqual((github.latest, github.patched), ("2.0.0", [(2, {"make_latest": "true"})]))
        self.assertIn("↺ latest was 1.5.1; it is 2.0.0 again, the highest version", out)

    def test_latest_on_a_pre_release_moves_back(self):
        github = FakeGitHub([release("2.1.0-rc.1", 1), release("2.0.0", 2)], latest="2.1.0-rc.1")
        self.assertEqual(run(github, "2.1.0-rc.1")[0], 0)
        self.assertEqual(github.latest, "2.0.0")

    def test_a_release_that_fails_never_stays_latest(self):
        # Found by the end-to-end run: a 3.0.0 made by hand, with no asset, took latest as the highest
        # version, and releases/latest/download/SHA256SUMS would have answered 404.
        github = FakeGitHub([release("4.0.0", 1, {}), release("3.0.1", 2)], latest="4.0.0")
        code, out = run(github, "4.0.0")
        self.assertEqual(code, 1)
        self.assertEqual(github.latest, "3.0.1")
        self.assertIn("↺ latest was 4.0.0; it is 3.0.1 again, the highest version that passes, while 4.0.0 fails", out)
        self.assertIn("GitHub does not move it when the latest release is deleted", github.issues[0]["body"])

    def test_a_release_that_failed_never_takes_latest_back(self):
        # 3.0.0 failed its guard, which moved latest to 2.0.1; the guard of a later pre-release, or of
        # a line's release, must not hand latest back to the highest version, 3.0.0.
        for later in (release("3.0.1-rc.1", 3), release("1.5.2", 3)):
            with self.subTest(later=later["tag_name"]):
                github = FakeGitHub([release("3.0.0", 1, {}), release("2.0.1", 2)], latest="3.0.0")
                self.assertEqual(run(github, "3.0.0")[0], 1)
                self.assertEqual(github.latest, "2.0.1")
                github.releases_.append(later)
                github.tags[later["tag_name"]] = COMMIT
                code, out = run(github, later["tag_name"])
                self.assertEqual(code, 0, out)
                self.assertEqual(github.latest, "2.0.1")
                self.assertIn("✓ latest is 2.0.1, the highest version", out)

    def test_a_release_marked_pre_release_is_never_made_latest(self):
        # GitHub makes no pre-release latest: a 2.1.0 published with "Set as a pre-release" ticked is
        # passed over.
        github = FakeGitHub([release("2.1.0", 1, prerelease=True), release("2.0.0", 2)], latest="2.0.0")
        code, out = run(github, "2.1.0")
        self.assertEqual(code, 0, out)
        self.assertEqual((github.latest, github.patched), ("2.0.0", []))

    def test_latest_is_repaired_even_when_the_release_fails(self):
        github = FakeGitHub([release("1.5.1", 1, immutable=False), release("2.0.0", 2)], latest="1.5.1")
        self.assertEqual(run(github, "1.5.1")[0], 1)
        self.assertEqual(github.latest, "2.0.0")


class GhVerifyTests(unittest.TestCase):
    def test_the_command_it_runs(self):
        calls = []

        class Done:
            returncode, stdout, stderr = 1, "", "Error: verifying with issuer\nno attestation names the commit"

        real = guard.subprocess.run
        guard.subprocess.run = lambda args, **_: calls.append(args) or Done()
        try:
            why = guard.gh_verify(Path("/x/a.tar.gz"), "o/r", COMMIT, SIGNER)
        finally:
            guard.subprocess.run = real
        self.assertEqual(calls[0], ["gh", "attestation", "verify", "/x/a.tar.gz", "--repo", "o/r",
                                    "--source-digest", COMMIT, "--signer-workflow", SIGNER])
        self.assertEqual(why, "no attestation names the commit")


if __name__ == "__main__":
    unittest.main()
