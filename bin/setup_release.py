"""The repository settings the release cycle relies on (ADR-009 §3.10), applied or checked.

A repository's settings are not in the repository, so this script applies them: an administrator
runs it with their own token, through `gh`. It is idempotent — a setting that holds is left alone —
and `--check` reports every setting that differs, changing nothing, and exits non-zero if any does.

- The ruleset `release cycle`, on the default branch and every line's branch `*.x`:
  - changes through a pull request only, merged with a merge commit;
  - no force push, no deletion;
  - the required checks, by the names of their summary jobs, reported by GitHub Actions;
  - the head branch up to date with its base before it merges;
  - no bypass, for anyone, administrators included.
- Where the repository has a merge queue — GitHub offers it to organisations — the ruleset
  `release cycle: merge queue`: one pull request per group, merged with a merge commit. GitHub
  refuses a merge queue on a pattern such as `*.x`, so it names the default branch and each line's
  branch that exists: cutting a new line means running this script again, and `--check` says so.
- Immutable releases: on.
- Head branches deleted on merge.
- No other ruleset requiring checks of the default branch or of a line's: GitHub requires the
  checks of every ruleset, and an older one names jobs that may never report again. The script
  reports it and leaves it: removing someone's ruleset is theirs to do, by hand.

Standard library only; GitHub through `gh api`.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

# The summary jobs of the workflows that gate a pull request into the default branch, and the
# checks of the cycle itself. A matrix job's name is never one of them (§3.10).
DEFAULT_CHECKS = ("actions tests", "builds", "cli tests", "commit messages", "core tests", "release gate",
                  "repo checks", "runtime tests")
GITHUB_ACTIONS = 15368   # the app that reports a workflow's checks: a status posted by anyone else is not one
RULESET = "release cycle"
QUEUE_RULESET = "release cycle: merge queue"
BRANCHES = ["~DEFAULT_BRANCH", "refs/heads/*.x"]
LINE = re.compile(r"(0|[1-9][0-9]*)\.x")


class GhError(Exception):
    pass


class Gh:
    """GitHub, through the `gh` command and its user's token."""

    def api(self, path: str, method: str = "GET", body: Any = None) -> Any:
        args = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
        if body is not None:
            args += ["--input", "-"]
        out = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                             capture_output=True, text=True)
        if out.returncode != 0:
            # gh prints the API's answer on stdout — its `errors` say what failed — and its own line on stderr.
            raise GhError(f"{method} {path}: {' '.join(part.strip() for part in (out.stdout, out.stderr) if part.strip())}")
        return json.loads(out.stdout) if out.stdout.strip() else None

    def all(self, path: str) -> List[Any]:
        """Every page of a list."""
        items, page = [], 1
        separator = "&" if "?" in path else "?"
        while True:
            batch = self.api(f"{path}{separator}per_page=100&page={page}") or []
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1


def desired_ruleset(checks: Sequence[str]) -> Dict[str, Any]:
    return {"name": RULESET, "target": "branch", "enforcement": "active", "bypass_actors": [],
            "conditions": {"ref_name": {"include": list(BRANCHES), "exclude": []}},
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {"type": "pull_request", "parameters": {
                    "allowed_merge_methods": ["merge"],
                    "dismiss_stale_reviews_on_push": False,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_approving_review_count": 0,
                    "required_review_thread_resolution": False}},
                {"type": "required_status_checks", "parameters": {
                    "do_not_enforce_on_create": False,
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [{"context": c, "integration_id": GITHUB_ACTIONS} for c in sorted(checks)]}},
            ]}


def desired_queue(lines: Sequence[str]) -> Dict[str, Any]:
    return {"name": QUEUE_RULESET, "target": "branch", "enforcement": "active", "bypass_actors": [],
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"] + [f"refs/heads/{b}" for b in sorted(lines)],
                                        "exclude": []}},
            "rules": [{"type": "merge_queue", "parameters": {
                "check_response_timeout_minutes": 60,
                "grouping_strategy": "ALLGREEN",
                "max_entries_to_build": 1,
                "max_entries_to_merge": 1,
                "merge_method": "MERGE",
                "min_entries_to_merge": 1,
                "min_entries_to_merge_wait_minutes": 0}}]}


def _checks(params: Dict[str, Any]) -> List[str]:
    return sorted(f"{c.get('context')} ({c.get('integration_id', 'any app')})" for c in params.get("required_status_checks", []))


def ruleset_drift(desired: Dict[str, Any], actual: Optional[Dict[str, Any]]) -> List[str]:
    """How ``actual`` differs from ``desired``: every rule, parameter and condition that is off."""
    if actual is None:
        return [f"there is no ruleset named {desired['name']!r}"]
    drift = []
    if actual.get("enforcement") != "active":
        drift.append(f"it is {actual.get('enforcement')}, not active")
    if actual.get("bypass_actors"):
        drift.append(f"it lets {len(actual['bypass_actors'])} actor(s) bypass it, and should let nobody")
    want_refs = sorted(desired["conditions"]["ref_name"]["include"])
    include = sorted(actual.get("conditions", {}).get("ref_name", {}).get("include", []))
    if include != want_refs:
        drift.append(f"it applies to {include}, and should apply to {want_refs}")
    if actual.get("conditions", {}).get("ref_name", {}).get("exclude"):
        drift.append(f"it excludes {actual['conditions']['ref_name']['exclude']}, and should exclude nothing")
    have = {rule["type"]: rule.get("parameters", {}) for rule in actual.get("rules", [])}
    want = {rule["type"]: rule.get("parameters", {}) for rule in desired["rules"]}
    for kind, params in want.items():
        if kind not in have:
            drift.append(f"it has no {kind} rule")
            continue
        for key, value in params.items():
            if key == "required_status_checks":
                if _checks(have[kind]) != _checks(params):
                    missing = sorted(set(_checks(params)) - set(_checks(have[kind])))
                    extra = sorted(set(_checks(have[kind])) - set(_checks(params)))
                    drift.append(f"its required checks differ — missing {missing or 'none'}, not required here {extra or 'none'}")
            elif have[kind].get(key) != value:
                drift.append(f"its {kind} rule has {key} = {json.dumps(have[kind].get(key))}, and should have {json.dumps(value)}")
    for kind in sorted(set(have) - set(want)):
        drift.append(f"it has a {kind} rule, which the cycle does not set")
    return drift


@dataclass
class Setting:
    name: str
    drift: List[str]
    apply: Optional[Callable[[], None]]   # None: the script reports it, and leaves it to be done by hand


def ruleset_setting(gh: Gh, repository: str, name: str, desired: Dict[str, Any], found: List[Dict[str, Any]]) -> Setting:
    mine = [r for r in found if r.get("name") == desired["name"] and r.get("source_type", "Repository") == "Repository"]
    actual = gh.api(f"repos/{repository}/rulesets/{mine[0]['id']}") if mine else None

    def apply():
        if actual is None:
            gh.api(f"repos/{repository}/rulesets", "POST", desired)
        else:
            gh.api(f"repos/{repository}/rulesets/{actual['id']}", "PUT", desired)

    return Setting(name, ruleset_drift(desired, actual), apply)


def other_rulesets(gh: Gh, repository: str, found: List[Dict[str, Any]], default: str, lines: Sequence[str]) -> List[Setting]:
    """Every other active ruleset that requires checks of the default branch or of a line's."""
    refs = [f"refs/heads/{b}" for b in [default, "0.x", *lines]]
    result = []
    for summary in found:
        if summary.get("name") in (RULESET, QUEUE_RULESET) or summary.get("target", "branch") != "branch":
            continue
        ruleset = gh.api(f"repos/{repository}/rulesets/{summary['id']}")
        if ruleset.get("target", "branch") != "branch":
            continue
        include = ruleset.get("conditions", {}).get("ref_name", {}).get("include", [])
        on_cycle = any(p in ("~DEFAULT_BRANCH", "~ALL") or any(fnmatch.fnmatchcase(r, p) for r in refs) for p in include)
        checks = [c.get("context") for rule in ruleset.get("rules", []) if rule.get("type") == "required_status_checks"
                  for c in rule.get("parameters", {}).get("required_status_checks", [])]
        if ruleset.get("enforcement") == "active" and on_cycle and checks:
            result.append(Setting(f"the ruleset {ruleset.get('name')!r}, which the cycle does not set", [
                f"it requires {len(checks)} check(s) of its own — {', '.join(checks)}: GitHub requires every "
                "ruleset's, so remove it by hand"], None))
    return result


def settings(gh: Gh, repository: str, checks: Sequence[str]) -> List[Setting]:
    repo = gh.api(f"repos/{repository}")
    found = gh.api(f"repos/{repository}/rulesets?includes_parents=false") or []
    result = [ruleset_setting(gh, repository, f"the ruleset {RULESET!r}, on the default branch and *.x",
                              desired_ruleset(checks), found)]
    lines = [b["name"] for b in gh.all(f"repos/{repository}/branches") if LINE.fullmatch(b["name"])]
    if repo.get("owner", {}).get("type") == "Organization":
        on = ", ".join(["the default branch"] + sorted(lines))
        result.append(ruleset_setting(gh, repository, f"the ruleset {QUEUE_RULESET!r}, on {on}",
                                      desired_queue(lines), found))
    immutable = (gh.api(f"repos/{repository}/immutable-releases") or {}).get("enabled") is True
    result.append(Setting("immutable releases", [] if immutable else ["they are off"],
                          lambda: gh.api(f"repos/{repository}/immutable-releases", "PUT")))
    result.append(Setting("head branches deleted on merge", [] if repo.get("delete_branch_on_merge") is True else ["they are kept"],
                          lambda: gh.api(f"repos/{repository}", "PATCH", {"delete_branch_on_merge": True})))
    return result + other_rulesets(gh, repository, found, repo.get("default_branch", "main"), lines)


def main(argv: Optional[Sequence[str]] = None, gh: Optional[Gh] = None) -> int:
    parser = argparse.ArgumentParser(prog="bin/setup-release.sh", description=__doc__.split("\n\n")[0])
    parser.add_argument("repository", help="OWNER/NAME")
    parser.add_argument("--check", action="store_true", help="report what differs, change nothing")
    parser.add_argument("--require", action="append", metavar="CHECK",
                        help="a required check, by name; repeat it. Default: Cortex's summary jobs")
    args = parser.parse_args(argv)
    gh = gh or Gh()
    checks = args.require or list(DEFAULT_CHECKS)

    try:
        found = settings(gh, args.repository, checks)
    except GhError as error:
        print(f"setup-release: {error}", file=sys.stderr)
        return 2
    drifted = [s for s in found if s.drift]
    for setting in found:
        if not setting.drift:
            print(f"✓ {setting.name}")
            continue
        print(f"✗ {setting.name}")
        for line in setting.drift:
            print(f"    {line}")
    if args.check:
        print(f"{len(drifted)} setting(s) differ." if drifted else "Every setting holds.")
        return 1 if drifted else 0
    if not any(s.name.startswith(f"the ruleset {QUEUE_RULESET!r}") for s in found):
        print("No merge queue: GitHub offers it to repositories of organisations. The gate runs again each night instead.")
    by_hand = [s for s in drifted if s.apply is None]
    for setting in drifted:
        if setting.apply is None:
            continue
        try:
            setting.apply()
        except GhError as error:
            print(f"setup-release: could not set {setting.name}: {error}", file=sys.stderr)
            return 2
        print(f"→ set {setting.name}")
    changed = len(drifted) - len(by_hand)
    print(f"{changed} setting(s) changed." if changed else "Nothing to change.")
    for setting in by_hand:
        print(f"! {setting.name}: left to you — remove it by hand, in the repository's Settings → Rules")
    return 1 if by_hand else 0


if __name__ == "__main__":
    sys.exit(main())
