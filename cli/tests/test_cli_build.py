"""``cli/build.py`` — what a release ships besides the binaries (ADR-008 §3.1, §3.3)."""

import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the fixture, not a package named tests
from release_fixture import build  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def tracked(*trees):
    out = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", *trees], capture_output=True, check=True).stdout
    return sorted(name for name in out.decode("utf-8").split("\0") if name)


@unittest.skipIf(shutil.which("git") is None or not (REPO / ".git").exists(), "needs a git checkout")
class SpecArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-build-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def members(self):
        with tarfile.open(build.spec_archive(self.tmp)) as archive:
            return archive.getmembers()

    def test_it_holds_exactly_the_three_trees(self):
        self.assertEqual({m.name.split("/")[0] for m in self.members()}, {"agents", "templates", "docs"})

    def test_it_holds_what_git_tracks_and_nothing_else(self):
        # From the commit, never the working copy: a file nobody committed — the active-theme
        # marker setup.sh writes, a draft — does not ship.
        stray = REPO / "docs" / "cortex-build-test-stray.md"
        stray.write_text("not committed\n", encoding="utf-8")
        self.addCleanup(stray.unlink)
        files = sorted(m.name for m in self.members() if m.isfile())
        self.assertEqual(files, tracked("agents", "templates", "docs"))

    def test_nothing_in_it_is_a_link_or_leaves_its_tree(self):
        for member in self.members():
            with self.subTest(member=member.name):
                self.assertTrue(member.isfile() or member.isdir())
                self.assertFalse(member.name.startswith("/") or ".." in member.name.split("/"))


class PackageTests(unittest.TestCase):
    def test_an_archive_is_the_same_bytes_for_the_same_source_date(self):
        # SOURCE_DATE_EPOCH sets every time in the archive — the gzip header's too.
        tmp = Path(tempfile.mkdtemp(prefix="cortex-build-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        binary = tmp / "cortex"
        binary.write_bytes(b"binary")
        digests = []
        for _ in range(2):
            with unittest.mock.patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "1790000000"}):
                digests.append(hashlib.sha256(build.package(binary, "linux-x86_64").read_bytes()).hexdigest())
            time.sleep(1.1)
        self.assertEqual(digests[0], digests[1])


class ChecksumsTests(unittest.TestCase):
    def test_sha256sums_reads_as_sha256sum_writes_it(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-build-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "cortex-a.tar.gz").write_bytes(b"a")
        (tmp / "cortex-b.zip").write_bytes(b"")
        (tmp / "unrelated.txt").write_bytes(b"x")
        self.assertEqual(build.checksums(tmp).read_bytes(), (
            b"ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb  cortex-a.tar.gz\n"
            b"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  cortex-b.zip\n"))


if __name__ == "__main__":
    unittest.main()


class _FakeApi:
    """GitHub's releases API, as fetch_known_specs reads it: pages of releases, and the files
    their assets name."""

    def __init__(self, pages, files):
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        routes = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = routes.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        for number, releases in enumerate([*pages, []], start=1):
            for release in releases:
                for asset in release.get("assets", []):
                    asset["browser_download_url"] = f"{outer.url}/files/{release['tag_name']}/{asset['name']}"
            routes[f"/repos/o/r/releases?per_page=100&page={number}"] = json.dumps(releases).encode()
        for (tag, name), body in files.items():
            routes[f"/files/{tag}/{name}"] = body
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def release(tag, *assets, draft=False, prerelease=False):
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease, "assets": [{"name": a} for a in assets]}


class FetchKnownSpecsTests(unittest.TestCase):
    A, B, C = "a" * 64, "b" * 64, "c" * 64

    def fetch(self, pages, files):
        api = _FakeApi(pages, files)
        self.addCleanup(api.close)
        return build.fetch_known_specs("o/r", api=api.url)

    def test_every_page_every_release_with_its_archive(self):
        pages = [[release("1.1.0", "SHA256SUMS"), release("1.0.0", "SHA256SUMS")],
                 [release("1.0.0-rc.1", "SHA256SUMS", prerelease=True), release("0.10.1")]]
        files = {("1.1.0", "SHA256SUMS"): f"{self.A}  cortex-linux-x86_64.tar.gz\n{self.B.upper()}  cortex-spec.tar.gz\n".encode(),
                 ("1.0.0", "SHA256SUMS"): f"{self.C} *cortex-spec.tar.gz\n".encode(),
                 ("1.0.0-rc.1", "SHA256SUMS"): f"{self.A}  cortex-spec.tar.gz\n".encode()}
        self.assertEqual(self.fetch(pages, files), {"1.1.0": self.B, "1.0.0": self.C, "1.0.0-rc.1": self.A})

    def test_drafts_and_tags_that_are_no_version_are_left_out(self):
        pages = [[release("1.2.0", draft=True), release("nightly", "SHA256SUMS"), release("0.9.0")]]
        self.assertEqual(self.fetch(pages, {("nightly", "SHA256SUMS"): b"x  cortex-spec.tar.gz\n"}), {})

    def test_a_release_from_1_0_0_without_its_archive_fails_the_build(self):
        # Skipped in silence, the binary would check that version against its SHA256SUMS alone.
        for pages, files, message in (
                ([[release("1.0.1")]], {}, "release 1.0.1 has no SHA256SUMS"),
                ([[release("1.0.1", "SHA256SUMS")]], {("1.0.1", "SHA256SUMS"): f"{self.A}  cortex.zip\n".encode()},
                 "lists no cortex-spec.tar.gz")):
            with self.subTest(message=message):
                with self.assertRaisesRegex(build.KnownSpecsError, message):
                    self.fetch(pages, files)

    def test_the_module_a_build_writes_holds_the_table(self):
        namespace = {}
        exec(build.known_specs_module({"1.1.0": self.B, "1.0.0": self.A}), namespace)
        self.assertEqual(namespace["KNOWN"], {"1.0.0": self.A, "1.1.0": self.B})


class VersionReportTests(unittest.TestCase):
    """``cortex --version --verbose`` says which spec archives the binary knows — what CI checks
    of each binary it builds."""

    def report(self, known):
        import io
        from contextlib import redirect_stdout

        sys.path[:0] = [str(REPO / "cli"), str(REPO / "core")]
        from cortex_cli import main, store

        out = io.StringIO()
        with unittest.mock.patch.object(store, "known_specs", return_value=known), redirect_stdout(out):
            self.assertEqual(main.main(["--version", "--verbose"]), 0)
        return out.getvalue().splitlines()

    def test_the_table_it_carries(self):
        lines = self.report({"1.1.0": "b" * 64, "1.0.0": "a" * 64})
        self.assertEqual(lines[1:], ["known spec archives: 2", f"  1.0.0  {'a' * 64}", f"  1.1.0  {'b' * 64}"])

    def test_none_is_said(self):
        self.assertTrue(self.report({})[1].startswith("known spec archives: 0 — "))
