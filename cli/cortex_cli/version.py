"""The version of the command — the release's, stamped at build time from the tag (ADR-008 §3.1).

``cli/build.py`` writes ``_stamp.py`` for the duration of a build. A source checkout has none:
it is no release, and says so — unless its tests name the version it stands for, with
``CORTEX_SOURCE_VERSION``. A build always has a stamp, and never reads that variable.
"""

import os

try:
    from ._stamp import VERSION
except ImportError:
    VERSION = os.environ.get("CORTEX_SOURCE_VERSION") or "0.0.0-dev"
