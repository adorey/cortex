"""Versions, as Semantic Versioning orders them (semver.org §11).

A version is ``X.Y.Z``, or ``X.Y.Z-identifiers`` for a pre-release; build metadata (``+…``) is not
accepted, since a version names a tag. A release is cut as ``X.Y.Z``, a pre-release as
``X.Y.Z-(alpha|beta|rc).N``: lowercase, the number after a dot, so that ``rc.10`` comes after
``rc.2``. Precedence is never ``sort -V``'s, which puts ``1.3.0`` before ``1.3.0-beta.1``.

Standard library only, like every script of these actions: they carry nothing of the project that
calls them. ``tests/semver-cases.json`` is the table every implementation of this ordering in the
repository is checked against.
"""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Iterable, Optional, Tuple

_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_CORE = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
VERSION = re.compile(rf"{_CORE}(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?", re.ASCII)
# The stages a pre-release is cut at, in their order.
STAGES = ("alpha", "beta", "rc")
PRERELEASE = re.compile(rf"{_CORE}-(alpha|beta|rc)\.(0|[1-9][0-9]*)", re.ASCII)


@total_ordering
class Version:
    def __init__(self, text: str):
        match = VERSION.fullmatch(text) if isinstance(text, str) else None
        if not match:
            raise ValueError(f"not a version: {text!r}")
        self.text = text
        self.core: Tuple[int, int, int] = tuple(int(part) for part in match.group(1, 2, 3))  # type: ignore[assignment]
        self.pre: Tuple[str, ...] = tuple(match.group(4).split(".")) if match.group(4) else ()

    @staticmethod
    def parse(text: object) -> Optional["Version"]:
        """The version ``text`` names, or None."""
        try:
            return Version(text)  # type: ignore[arg-type]
        except ValueError:
            return None

    @property
    def major(self) -> int:
        return self.core[0]

    @property
    def is_release(self) -> bool:
        """``X.Y.Z``, with no suffix."""
        return not self.pre

    @property
    def release(self) -> "Version":
        """The release a pre-release prepares: ``1.3.0`` for ``1.3.0-rc.1``."""
        return Version("%d.%d.%d" % self.core)

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


def is_release(text: object) -> bool:
    """``text`` is ``X.Y.Z``, with no suffix."""
    version = Version.parse(text)
    return version is not None and version.is_release


def is_prerelease(text: object) -> bool:
    """``text`` is a pre-release as one is cut: ``X.Y.Z-(alpha|beta|rc).N``."""
    return isinstance(text, str) and PRERELEASE.fullmatch(text) is not None


def highest(versions: Iterable[Version]) -> Optional[Version]:
    return max(versions, default=None)
