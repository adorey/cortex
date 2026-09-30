"""``cli/build.py`` — what a release ships besides the binaries (ADR-008 §3.1, §3.3)."""

import hashlib
import importlib.util
import shutil
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

CLI = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("cortex_build", CLI / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


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


if __name__ == "__main__":
    unittest.main()
