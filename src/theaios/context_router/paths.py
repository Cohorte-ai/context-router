"""Path patterns for include, exclude and deny lists.

Patterns use ``fnmatch`` syntax (``*`` also matches ``/``), with one addition: ``**/`` also
matches zero folders. Without it, ``**/secrets/**`` missed a ``secrets/`` folder at the top of
a source and the default ``**/*`` skipped top-level files.
"""

from __future__ import annotations

import fnmatch
from functools import lru_cache


@lru_cache(maxsize=1024)
def _variants(pattern: str) -> tuple[str, ...]:
    variants = {pattern}
    while True:
        more = {
            v[:i] + v[i + 3 :]
            for v in variants
            for i in range(len(v))
            if v.startswith("**/", i) and (i == 0 or v[i - 1] == "/")
        }
        if more <= variants:
            return tuple(sorted(variants))
        variants |= more


def path_matches(path: str, pattern: str) -> bool:
    """True if ``path`` (relative, ``/``-separated) matches ``pattern``."""
    path = path.replace("\\", "/")
    return any(fnmatch.fnmatch(path, v) for v in _variants(pattern))


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(path_matches(path, p) for p in patterns)
