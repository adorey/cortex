"""``cortex validate`` — ADR-007's validator, run by the command (ADR-008 §3.8).

Same checks, same report, same exit codes as ``bin/validate-overlays.sh``: the options are the
core's own, and the core parses them.

Until ``cortex sync`` records where the spec is (ADR-008 phase 2), the project is the current
directory and its base the ``cortex/`` directory in it — where a submodule puts the spec, and
where the script found it.
"""

from __future__ import annotations

from typing import List

from cortex_core import validate

from .paths import working_directory


def run(args: List[str]) -> int:
    project = working_directory()
    return validate.main(args, project_root=project, base_root=f"{project}/cortex", prog="cortex validate")
