"""The draft: created last, never rebuilt from another commit, its own made again (ADR-009 §3.3)."""

import http.client
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import draft as rd  # noqa: E402
from github import GitHubError  # noqa: E402

TARGET = "a" * 40
SIX = ["SHA256SUMS", "cortex-linux-aarch64.tar.gz", "cortex-linux-x86_64.tar.gz", "cortex-macos-arm64.tar.gz",
       "cortex-spec.tar.gz", "cortex-windows-x86_64.zip"]


class FakeGitHub:
    def __init__(self, releases=(), fail_upload_after=None, upload_error=None):
        self.releases_ = {r["id"]: dict(r, assets=list(r.get("assets", []))) for r in releases}
        self.calls = []
        self.fail_upload_after = fail_upload_after
        self.upload_error = upload_error or GitHubError(502, "upload cut")
        self.uploads = 0

    def repo(self, suffix=""):
        return f"/repos/o/r{suffix}"

    def releases(self):
        return list(self.releases_.values())

    def get(self, path):
        rid = int(path.split("/releases/")[1].split("/")[0])
        return [{"name": a["name"], "size": a["size"]} for a in self.releases_[rid]["assets"]]

    def request(self, method, path, body=None, data=None, content_type=None, url=None):
        self.calls.append((method, path or url))
        if method == "DELETE":
            del self.releases_[int(path.rsplit("/", 1)[1])]
            return None
        if method == "POST" and path == "/repos/o/r/releases":
            rid = max(self.releases_, default=0) + 1
            self.releases_[rid] = dict(body, id=rid, assets=[], upload_url=f"https://uploads/{rid}/assets{{?name,label}}",
                                       html_url=f"https://github.com/o/r/releases/tag/untagged-{rid}")
            return self.releases_[rid]
        if method == "POST" and url:
            if self.fail_upload_after is not None and self.uploads >= self.fail_upload_after:
                raise self.upload_error
            self.uploads += 1
            rid = int(url.split("https://uploads/")[1].split("/")[0])
            self.releases_[rid]["assets"].append({"name": url.split("name=")[1], "size": len(data)})
            return {}
        raise AssertionError((method, path, url))


class DraftTests(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="release-draft-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.dir = root / "assets"
        self.dir.mkdir()
        for name in SIX:
            (self.dir / name).write_bytes(name.encode() * 3)
        self.body = root / "body.md"
        self.body.write_text("# 1.4.0", encoding="utf-8")

    def run_draft(self, github, *extra, version="1.4.0", target=TARGET):
        out = io.StringIO()
        with redirect_stdout(out):
            code = rd.main(["--version", version, "--target", target, "--body-file", str(self.body),
                            "--assets", str(self.dir), "--expected", "\n".join(SIX), "--latest", "true", *extra],
                           github=github)
        return code, out.getvalue()

    def test_a_draft_with_its_six_assets_its_note_and_its_commit(self):
        github = FakeGitHub()
        code, out = self.run_draft(github)
        self.assertEqual(code, 0, out)
        (release,) = github.releases()
        self.assertEqual((release["tag_name"], release["name"], release["draft"], release["target_commitish"],
                          release["body"], release["prerelease"], release["make_latest"]),
                         ("1.4.0", "1.4.0", True, TARGET, "# 1.4.0", False, "true"))
        self.assertEqual(sorted(a["name"] for a in release["assets"]), SIX)
        self.assertIn("The draft release 1.4.0 is ready, with 6 assets", out)

    def test_a_pre_release_draft_is_never_latest(self):
        github = FakeGitHub()
        self.run_draft(github, "--prerelease", "true", "--latest", "false", version="1.4.0-rc.1")
        (release,) = github.releases()
        self.assertEqual((release["prerelease"], release["make_latest"]), (True, "false"))

    def test_missing_assets_stop_before_anything_is_created(self):
        (self.dir / "SHA256SUMS").unlink()
        github = FakeGitHub()
        code, out = self.run_draft(github)
        self.assertEqual((code, github.calls), (1, []))
        self.assertIn("missing ['SHA256SUMS']", out)

    def test_a_published_release_changes_nothing(self):
        github = FakeGitHub([{"id": 9, "tag_name": "1.4.0", "draft": False, "target_commitish": TARGET}])
        code, out = self.run_draft(github)
        self.assertEqual((code, github.calls), (1, []))
        self.assertIn("1.4.0 is already published: nothing is changed", out)

    def test_a_draft_of_another_commit_changes_nothing(self):
        github = FakeGitHub([{"id": 9, "tag_name": "1.4.0", "draft": True, "target_commitish": "b" * 40}])
        code, out = self.run_draft(github)
        self.assertEqual((code, github.calls), (1, []))
        self.assertIn("a draft 1.4.0 of another commit", out)

    def test_a_run_cut_while_uploading_then_its_re_run_leave_one_complete_draft(self):
        # GitHub answering an error, or the connection cut under the upload.
        for error in (GitHubError(502, "upload cut"), ConnectionResetError(104, "Connection reset by peer"),
                      http.client.IncompleteRead(b"")):
            with self.subTest(error=type(error).__name__):
                github = FakeGitHub(fail_upload_after=3, upload_error=error)
                code, out = self.run_draft(github)
                self.assertEqual(code, 1)
                self.assertIn("the draft 1.4.0 holds at least 3 of 6 assets: do not publish it — run the job again", out)
                (half,) = github.releases()
                self.assertEqual((half["draft"], len(half["assets"])), (True, 3))
                github.fail_upload_after = None
                code, out = self.run_draft(github)
                self.assertEqual(code, 0, out)
                self.assertIn("left by a run that failed, is made again", out)
                (release,) = github.releases()
                self.assertEqual(sorted(a["name"] for a in release["assets"]), SIX)


if __name__ == "__main__":
    unittest.main()
