#!/usr/bin/env bash
#
# Creates (or updates) the labels used to deliver multi-phase ADRs.
#
# The issue board is the changelog of an ADR: `adr:NNN` sorts by decision record,
# `phase:N` sorts by phase within it, and `type:*` says which part of Cortex a task
# touches. The three issue kinds (`adr-epic`, `adr-phase`, `adr-task`) carry the
# hierarchy described in docs/process/adr-implementation.md.
#
# The wave an ADR belongs to on the roadmap is deliberately NOT a label: it is a field
# of the GitHub Project, because it moves every time the roadmap is re-planned and a
# label would silently drift from it.
#
# Idempotent: `gh label create --force` updates an existing label instead of failing,
# so running this twice is safe, and re-running it after a colour change applies it.
#
# Usage:
#   bin/setup-labels.sh                     # current repository
#   bin/setup-labels.sh --repo owner/name   # another repository
#   bin/setup-labels.sh --dry-run           # print what would be created

set -eo pipefail

repo_args=()
dry_run=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) repo_args=(--repo "$2"); shift 2 ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done

# --- Colors ----------------------------------------------------------------
if [[ -t 1 ]]; then
    GREEN='\033[0;32m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
else
    GREEN=''; RED=''; BLUE=''; NC=''
fi

if ! command -v gh >/dev/null 2>&1; then
    printf "${RED}This script needs the GitHub CLI: https://cli.github.com${NC}\n" >&2
    exit 2
fi

if [[ "$dry_run" -eq 0 ]] && ! gh auth status >/dev/null 2>&1; then
    printf "${RED}Not authenticated. Run: gh auth login${NC}\n" >&2
    exit 2
fi

# name|colour|description
labels=(
    # Issue kind — the three levels below the roadmap Project
    "adr-epic|0e3a6e|Roadmap item: one ADR, from proposal to implementation"
    "adr-phase|0052cc|Parent issue tracking one numbered phase of an ADR"
    "adr-task|006b75|Sub-issue: one testable task inside an ADR phase"

    # Decision record. Add one line per ADR entering implementation.
    "adr:007|7057ff|ADR-007 - Cortex Core, unified cascade resolution"

    # Phase within the ADR. The number is the ADR's own, not the execution order.
    "phase:1|c5def5|ADR phase 1"
    "phase:2|9edcf5|ADR phase 2"
    "phase:3|6cb6f5|ADR phase 3"
    "phase:4|3f9bf0|ADR phase 4"
    "phase:5|1f7ad6|ADR phase 5"
    "phase:6|0b5cad|ADR phase 6"
    "phase:7|0a4a8c|ADR phase 7"
    "phase:8|07356b|ADR phase 8"

    # Part of Cortex the task touches. spec / core / runtime mirror the ADR-002 firewall:
    # a task that needs two of them is usually two tasks.
    "type:spec|c2e0c6|The Markdown cascade: roles, capabilities, personalities, workflows"
    "type:core|bfdadc|cortex-core, the CLI, packaging and distribution"
    "type:runtime|1d76db|The engine: API, agentic loop, stores, security gate"
    "type:test|0e8a16|Tests, fixtures, validators, test tooling"
    "type:security|b60205|Security hardening or a security finding"
    "type:perf|fbca04|Optimisation or a performance finding"
    "type:docs|0075ca|Documentation, ADR amendment, release note"
    "type:infra|5319e7|Docker, CI, deployment, configuration"

    # State
    "gate:blocking|d93f0b|Must land before the ADR release gate - never deferred"
    "status:blocked|e99695|Waiting on something outside the issue; the comment says what"
)

created=0
for entry in "${labels[@]}"; do
    IFS='|' read -r name colour description <<< "$entry"

    if [[ "$dry_run" -eq 1 ]]; then
        printf '  would create  %-16s #%s  %s\n' "$name" "$colour" "$description"
        continue
    fi

    gh label create "$name" \
        --color "$colour" \
        --description "$description" \
        --force \
        "${repo_args[@]+"${repo_args[@]}"}" >/dev/null
    printf "  ${GREEN}ok${NC}  %-16s #%s\n" "$name" "$colour"
    created=$((created + 1))
done

if [[ "$dry_run" -eq 1 ]]; then
    printf "\n${BLUE}%s label(s) would be created or updated.${NC}\n" "${#labels[@]}"
else
    printf "\n${BLUE}%s label(s) created or updated.${NC}\n" "$created"
fi
