#!/usr/bin/env bash
#
# Fails when tracked content is not written in English.
#
# Cortex is public and its files are read by both humans and language models. A French
# sentence in a role card is not only inconsistent — it silently changes what the model is
# primed to produce, and that drift is invisible in review because no single line looks
# wrong.
#
# Two independent nets, because neither catches everything on its own:
#   1. accented characters, including uppercase;
#   2. a short list of words that exist in French and not in English, since a French
#      sentence can carry no accent at all.
#
# Escape hatch: append `english-check:ignore` in a comment on the offending line. Cortex has
# genuine exceptions — a documented convention term, a language label in a theme file — and
# they are expected to be marked, not hidden by weakening the patterns.
#
# Usage:
#   bin/check-english.sh            # check tracked files
#   bin/check-english.sh --list     # list scanned files and exit

set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 2

ACCENTS='[éèêëàâäùûüôöîïçœÉÈÊËÀÂÄÙÛÜÔÖÎÏÇŒ]'

FRENCH_WORDS='\b([Ll]es|[Dd]es|[Uu]ne|[Pp]our|[Aa]vec|[Dd]ans|[Cc]ette|[Aa]ucun|[Aa]ucune|[Ss]inon|[Dd]onc|[Cc]haque|[Ll]orsque|[Aa]fin|[Dd]ont|[Ll]eur|[Nn]ous|[Vv]ous|[Ee]nsuite|[Pp]uis|[Aa]lors|[Tt]oujours|[Jj]amais|[Rr]emplace|[Rr]etourne|[Ii]ndique|[Ee]xécute|[Aa]ttend)\b'

is_excluded() {
    case "$1" in
        runtime/.venv/*|runtime/*.egg-info/*|var/*) return 0 ;;
        LICENSE|NOTICE) return 0 ;;
        *.png|*.jpg|*.jpeg|*.gif|*.ico|*.woff|*.woff2|*.pdf) return 0 ;;
        bin/check-english.sh) return 0 ;;  # this file documents the patterns it forbids
    esac
    return 1
}

files=()
while IFS= read -r f; do
    is_excluded "$f" && continue
    [ -f "$f" ] || continue
    files+=("$f")
done < <(git ls-files)

if [ "${1:-}" = "--list" ]; then
    printf '%s\n' "${files[@]}"
    exit 0
fi

hits=0
for f in "${files[@]}"; do
    while IFS= read -r line; do
        case "$line" in *english-check:ignore*) continue ;; esac
        printf '%s\n' "$line"
        hits=$((hits + 1))
    done < <(grep -nIE "$ACCENTS|$FRENCH_WORDS" "$f" 2>/dev/null | sed "s|^|$f:|")
done

if [ "$hits" -gt 0 ]; then
    printf '\n\033[31m%s\033[0m\n' "✗ $hits line(s) look like they are not in English."
    cat <<'EOF'

Cortex is public, and its layers prime a language model: code, comments, agent cards,
documentation and console output are in English. See the "Style & conventions" section of
CONTRIBUTING.md.

If a line is a legitimate exception — a documented convention term, a language label —
append `english-check:ignore` in a comment on that line.
EOF
    exit 1
fi

printf '\033[32m%s\033[0m\n' "✓ ${#files[@]} tracked files scanned, all English."
