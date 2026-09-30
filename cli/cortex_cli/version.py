"""The version of the command — the release's, stamped at build time from the tag (ADR-008 §3.1).

``cli/build.py`` writes ``_stamp.py`` for the duration of a build. A source checkout has none:
it is no release, and says so.
"""

try:
    from ._stamp import VERSION
except ImportError:
    VERSION = "0.0.0-dev"
