#!/usr/bin/env bash
#
# Applies the repository settings the release cycle relies on (ADR-009 §3.10), or checks them:
# the ruleset of the default branch and of every line's branch `*.x` — pull requests only, merge
# commits only, no force push, no deletion, the required checks by their summary jobs, up to date
# before merging, the merge queue where the repository has one, no bypass for anyone — immutable
# releases, and head branches deleted on merge. Another ruleset that requires checks there is
# reported, and left to be removed by hand.
#
# Run it as an administrator, with your own `gh` login: CI has no administrator rights, and should
# not. Idempotent: a setting that holds is left alone, so a second run changes nothing.
#
# Usage:
#   bin/setup-release.sh OWNER/NAME                  # apply what differs; exit 1 if a ruleset is left to you
#   bin/setup-release.sh OWNER/NAME --check          # report what differs, change nothing; exit 1 if any
#   bin/setup-release.sh OWNER/NAME --require "ci"   # another repository's required checks, repeated
#
# The logic is bin/setup_release.py, standard library Python: comparing a ruleset is JSON work.

set -eo pipefail

if ! command -v gh >/dev/null 2>&1; then
    printf 'setup-release: gh is needed — https://cli.github.com\n' >&2
    exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
    printf 'setup-release: python3 is needed\n' >&2
    exit 2
fi
case "${1:-}" in
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

exec python3 "$(dirname "$0")/setup_release.py" "$@"
