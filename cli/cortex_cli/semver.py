"""Versions, as Semantic Versioning orders them — releases and pre-releases (ADR-008 §3.3).

A version is ``X.Y.Z``, or ``X.Y.Z-pre.release`` for a build of no release. Build metadata
(``+…``) is not accepted: a version names a directory of the store.
"""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Tuple

_IDENTIFIER = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
_VERSION = re.compile(rf"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?$")


@total_ordering
class Version:
    def __init__(self, text: str):
        match = _VERSION.match(text)
        if not match:
            raise ValueError(f"not a version: {text!r}")
        self.text = text
        self.core = tuple(int(part) for part in match.group(1, 2, 3))
        self.pre = tuple(match.group(4).split(".")) if match.group(4) else ()

    @staticmethod
    def valid(text: str) -> bool:
        return bool(_VERSION.match(text))

    def _key(self) -> Tuple:
        # A pre-release comes before its release; its identifiers compare numerically when they
        # are numbers, lexically otherwise, a number before a word (semver.org §11).
        pre = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in self.pre)
        return self.core, (0, pre) if self.pre else (1, ())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self._key() == other._key()

    def __lt__(self, other: "Version") -> bool:
        return self._key() < other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"Version({self.text!r})"


# The first release published with a spec archive (ADR-008 §3.3): no older one can be downloaded.
FIRST_SPEC_ARCHIVE = Version("1.0.0")
