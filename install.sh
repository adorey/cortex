#!/bin/sh
# ============================================================================
# Cortex — install.sh: the one-line install on Linux and macOS (ADR-008 §3.2)
# ============================================================================
#
#   curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- 1.0.0
#   curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- --name cortex
#
# Downloads the release asset of this machine — the latest release, or the version given —
# checks it against the release's SHA256SUMS and stops on a mismatch, then installs the
# `cortex` binary into ~/.cortex/bin. It needs no administrator right, and edits no file of
# yours: it prints the line to add to your shell profile. Run it again to upgrade.
#
# When another `cortex` command comes first on PATH, the binary is installed as `cortex-ai`
# instead; `--name cortex` installs it as `cortex` anyway.
#
# Environment:
#   CORTEX_HOME           where Cortex lives on this machine (default: ~/.cortex)
#   CORTEX_RELEASES_URL   where the releases are downloaded from (default: the GitHub
#                         releases of adorey/cortex) — a mirror serving the same layout,
#                         latest/download/ASSET and download/VERSION/ASSET, over https;
#                         http only to this machine (127.0.0.1, localhost), for tests
#
# POSIX sh, not Bash: dash runs it on Debian and Ubuntu.
# ============================================================================

set -eu

RELEASES_URL="${CORTEX_RELEASES_URL:-https://github.com/adorey/cortex/releases}"
CORTEX_HOME="${CORTEX_HOME:-$HOME/.cortex}"
VERSION=""
NAME=""

say() { printf '%s\n' "$*"; }
fail() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }

usage() {
    say "Usage: install.sh [VERSION] [--name cortex|cortex-ai]"
    say ""
    say "  VERSION        the release to install, X.Y.Z (default: the latest)"
    say "  --name NAME    install the command as NAME: cortex or cortex-ai"
    say "                 (default: cortex, or cortex-ai when another cortex comes first on PATH)"
}

# Everything runs from main(), called on the script's last line: piped from curl, a download
# cut short defines a function and runs nothing, where top-level commands would have run up to
# the cut.
main() {
    # --- Arguments -------------------------------------------------------------
    while [ $# -gt 0 ]; do
        case "$1" in
            --name)
                [ $# -ge 2 ] || fail "--name needs a value: cortex or cortex-ai"
                NAME="$2"
                shift 2
                ;;
            --name=*)
                NAME="${1#--name=}"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -*)
                usage >&2
                fail "unknown option: $1"
                ;;
            *)
                [ -z "$VERSION" ] || fail "one version at most (got $VERSION and $1)"
                VERSION="$1"
                shift
                ;;
        esac
    done

    # grep reads lines: a version holding a newline would pass on its first line alone.
    case "$VERSION" in
        *[!0-9A-Za-z.-]*) fail "not a version: $VERSION (expected X.Y.Z)" ;;
    esac
    if [ -n "$VERSION" ] && ! printf '%s\n' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$'; then
        fail "not a version: $VERSION (expected X.Y.Z)"
    fi
    case "$NAME" in
        ""|cortex|cortex-ai) ;;
        *) fail "--name is cortex or cortex-ai (got $NAME)" ;;
    esac
    # SHA256SUMS comes from where the archive does: it proves the download whole, not its origin.
    # That origin is https — or this machine, for a test — never a plain http elsewhere.
    case "$RELEASES_URL" in
        https://*|http://127.0.0.1|http://127.0.0.1[:/]*|http://localhost|http://localhost[:/]*) ;;
        *) fail "CORTEX_RELEASES_URL must be https:// — http:// only to 127.0.0.1 or localhost (got $RELEASES_URL)" ;;
    esac

    # --- This machine ------------------------------------------------------------
    os="$(uname -s)"
    machine="$(uname -m)"
    case "$os" in
        Linux)
            case "$machine" in
                x86_64|amd64) target="linux-x86_64" ;;
                aarch64|arm64) target="linux-aarch64" ;;
                *) fail "no build for Linux on $machine — the targets are x86_64 and aarch64" ;;
            esac
            ;;
        Darwin)
            # A shell running under Rosetta reports x86_64 on Apple silicon: ask the hardware.
            if [ "$machine" = arm64 ] || [ "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" = 1 ]; then
                target="macos-arm64"
            else
                fail "no build for Intel macOS — the macOS target is Apple silicon (arm64)"
            fi
            ;;
        *)
            fail "no build for $os here — on Windows, run install.ps1 in PowerShell"
            ;;
    esac
    asset="cortex-$target.tar.gz"

    # --- Tools -----------------------------------------------------------------
    if command -v curl >/dev/null 2>&1; then
        fetch() { curl --fail --silent --show-error --location --proto '=https,http' --proto-redir '=https' --retry 2 --output "$2" "$1"; }
    elif command -v wget >/dev/null 2>&1; then
        fetch() { wget --quiet --tries=3 --output-document="$2" "$1"; }
    else
        fail "needs curl or wget to download the release"
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        sha256() { sha256sum "$1" | cut -d ' ' -f 1; }
    elif command -v shasum >/dev/null 2>&1; then
        sha256() { shasum -a 256 "$1" | cut -d ' ' -f 1; }
    else
        fail "needs sha256sum or shasum to check the download"
    fi

    # --- Download and check ----------------------------------------------------
    if [ -n "$VERSION" ]; then
        base="$RELEASES_URL/download/$VERSION"
    else
        base="$RELEASES_URL/latest/download"
    fi

    bin_dir="$CORTEX_HOME/bin"
    mkdir -p "$CORTEX_HOME"
    # Next to the binary's final place: one file system, so that the last step is a rename.
    work="$(mktemp -d "$CORTEX_HOME/.install.XXXXXX")"
    trap 'rm -rf "$work"' EXIT
    trap 'exit 130' INT TERM

    say "Downloading $asset from $base"
    fetch "$base/SHA256SUMS" "$work/SHA256SUMS" || fail "could not download $base/SHA256SUMS"
    fetch "$base/$asset" "$work/$asset" || fail "could not download $base/$asset"

    expected="$(awk -v name="$asset" '$2 == name || $2 == "*" name { print $1; exit }' "$work/SHA256SUMS")"
    [ -n "$expected" ] || fail "SHA256SUMS lists no $asset — nothing was installed"
    actual="$(sha256 "$work/$asset")"
    expected="$(printf '%s' "$expected" | tr 'A-F' 'a-f')"
    if [ "$actual" != "$expected" ]; then
        fail "checksum mismatch for $asset — expected $expected, got $actual. Nothing was installed."
    fi

    mkdir "$work/unpacked"
    tar -xzf "$work/$asset" -C "$work/unpacked"
    [ -f "$work/unpacked/cortex" ] || fail "$asset holds no cortex binary — nothing was installed"
    chmod 755 "$work/unpacked/cortex"
    # Run once before it is installed, and say why when it cannot: the binary unpacks itself in
    # $TMPDIR at every start, so a noexec /tmp stops it as surely as an older glibc does.
    if ! installed_version="$("$work/unpacked/cortex" --version 2>"$work/run.err")"; then
        say "The binary does not run on this machine:" >&2
        sed 's/^/    /' "$work/run.err" >&2
        fail "it needs a 64-bit Linux with glibc 2.28 or later, or macOS on Apple silicon, and a TMPDIR it may execute from. Nothing was installed."
    fi

    # --- The command's name ----------------------------------------------------
    mkdir -p "$bin_dir"
    physical_dir() { (cd "$1" 2>/dev/null && pwd -P) || printf '%s\n' "$1"; }
    physical_bin_dir="$(physical_dir "$bin_dir")"
    # The cortex found first on PATH, unless it is this one — through a link or not: files are
    # compared by identity (-ef, which dash, busybox and bash 3.2 all have), not by directory.
    other_cortex() {
        found="$(command -v cortex 2>/dev/null || true)"
        # shellcheck disable=SC3013
        if [ -n "$found" ] && ! [ "$found" -ef "$bin_dir/cortex" ]; then
            printf '%s\n' "$found"
        fi
    }
    if [ -z "$NAME" ]; then
        # Installed before, it keeps its name: running the script again is the upgrade.
        if [ -e "$bin_dir/cortex" ]; then
            NAME="cortex"
        elif [ -e "$bin_dir/cortex-ai" ]; then
            NAME="cortex-ai"
        elif [ -n "$(other_cortex)" ]; then
            say "Another cortex command comes first on PATH: $(other_cortex)"
            say "Installing as cortex-ai instead — run the script with --name cortex to install as cortex anyway."
            NAME="cortex-ai"
        else
            NAME="cortex"
        fi
    fi

    # --- Install ---------------------------------------------------------------
    mv -f "$work/unpacked/cortex" "$bin_dir/$NAME"
    say "Installed $installed_version as $bin_dir/$NAME"
    if [ "$NAME" = cortex ] && [ -n "$(other_cortex)" ]; then
        say "note: another cortex command comes first on PATH, $(other_cortex): typing cortex runs it, not this one." >&2
    fi

    on_path=false
    old_ifs="$IFS"
    IFS=:
    set -f                      # PATH is split on ':', never expanded as a pattern
    for dir in $PATH; do
        if [ -n "$dir" ] && [ "$(physical_dir "$dir")" = "$physical_bin_dir" ]; then
            on_path=true
        fi
    done
    set +f
    IFS="$old_ifs"
    case "$on_path" in
        true) ;;
        *)
            say ""
            say "$bin_dir is not on your PATH. Add it in your shell's profile — ~/.profile, ~/.bashrc or ~/.zshrc:"
            say ""
            say "    export PATH=\"$bin_dir:\$PATH\""
            ;;
    esac
}

{ main "$@"; }
