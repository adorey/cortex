"""``cortex init`` — ``setup.sh``, at parity (ADR-008 §3.7, phase 4).

The matrix (``init_matrix``) is what ``setup.sh`` writes, captured. The script replays it, until
phase 5 deletes it.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import init_matrix as matrix  # noqa: E402

EXPECTED = json.loads(matrix.EXPECTED.read_text(encoding="utf-8"))
HAS_GIT = shutil.which("git") is not None


class CaptureTests(unittest.TestCase):
    def test_the_matrix_was_captured_for_every_case(self):
        self.assertEqual(sorted(EXPECTED), sorted(matrix.CASES))


@unittest.skipIf(os.name == "nt" or shutil.which("bash") is None or not HAS_GIT, "setup.sh is a Bash script")
@unittest.skipUnless((matrix.REPO / "setup.sh").is_file(), "setup.sh is gone")
class SetupShTests(unittest.TestCase):
    def test_setup_sh_still_writes_the_matrix(self):
        for case in matrix.CASES:
            with self.subTest(case=case):
                tmp = Path(tempfile.mkdtemp(prefix="cortex-init-"))
                try:
                    self.assertEqual(matrix.run_setup(case, tmp, matrix.build_spec(tmp)), EXPECTED[case])
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
