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
#                         latest/download/ASSET and download/VERSION/ASSET
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

    if [ -n "$VERSION" ] && ! printf '%s\n' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$'; then
        fail "not a version: $VERSION (expected X.Y.Z)"
    fi
    case "$NAME" in
        ""|cortex|cortex-ai) ;;
        *) fail "--name is cortex or cortex-ai (got $NAME)" ;;
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
        fetch() { curl --fail --silent --show-error --location --retry 2 --output "$2" "$1"; }
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
    # Next to the binary's final place: one file system, so the last step is a rename; and not
    # /tmp, which some systems mount noexec — the binary is run once before it is installed.
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
    installed_version="$("$work/unpacked/cortex" --version)" \
        || fail "the binary does not run on this machine — Linux needs glibc 2.28 or later. Nothing was installed."

    # --- The command's name ----------------------------------------------------
    mkdir -p "$bin_dir"
    # Directories are compared resolved: PATH may name one another way than CORTEX_HOME does.
    physical_dir() { (cd "$1" 2>/dev/null && pwd -P) || printf '%s\n' "$1"; }
    physical_bin_dir="$(physical_dir "$bin_dir")"
    if [ -z "$NAME" ]; then
        NAME="cortex"
        existing="$(command -v cortex 2>/dev/null || true)"
        if [ -n "$existing" ] && [ "$(physical_dir "$(dirname "$existing")")" != "$physical_bin_dir" ]; then
            say "Another cortex command comes first on PATH: $existing"
            say "Installing as cortex-ai instead — run the script with --name cortex to install as cortex anyway."
            NAME="cortex-ai"
        fi
    fi

    # --- Install ---------------------------------------------------------------
    mv -f "$work/unpacked/cortex" "$bin_dir/$NAME"
    say "Installed $installed_version as $bin_dir/$NAME"

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

main "$@"
