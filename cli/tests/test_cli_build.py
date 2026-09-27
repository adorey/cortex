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
