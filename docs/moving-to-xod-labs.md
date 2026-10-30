# Cortex moved to xod-labs

On 2026-10-30, Cortex moved from `adorey/cortex` to [`xod-labs/cortex`](https://github.com/xod-labs/cortex), the GitHub organisation of xod labs. GitHub redirects the old address, so nothing you set up before stops working. A few updates are recommended, depending on how you use Cortex.

## What keeps working

A test repository was transferred first, and read again through each of these old addresses:

| What you use | After the move |
| --- | --- |
| `cortex` 1.0.0 to 1.2.1, already installed: `cortex sync`, and the specs it downloads | Works, through the redirected address |
| The old install command, `raw.githubusercontent.com/adorey/cortex/…` | Works |
| Your projects: `cortex.toml` and `cortex.local.toml` | Unchanged |
| A clone of the repository: `git fetch`, `pull` and `push` | Works, through the redirect |
| Links to issues, pull requests, documentation and releases | Redirected |

## What to do

Everyone who installed `cortex` reinstalls it once, from the new address. The rest depends on how you use Cortex.

### You use `cortex`

Nothing is urgent. Once 1.2.2 is out, install it from the new address: from 1.2.2 on, the binary no longer depends on the redirect.

```bash
curl -fsSL https://raw.githubusercontent.com/xod-labs/cortex/main/install.sh | sh     # Linux, macOS
```

```powershell
irm https://raw.githubusercontent.com/xod-labs/cortex/main/install.ps1 | iex          # Windows PowerShell
```

`cortex --version` then prints 1.2.2. Your projects keep the version they pin: nothing changes in `cortex.toml`.

### You have a clone of the repository

Point it at the new address:

```bash
git remote set-url origin git@github.com:xod-labs/cortex.git     # or https://github.com/xod-labs/cortex.git
git remote -v
```

A fork stays attached to Cortex: point its `upstream` remote at the new address the same way.

### A script, a CI job or a provisioning downloads Cortex

Replace `github.com/adorey/cortex` with `github.com/xod-labs/cortex`, and `raw.githubusercontent.com/adorey/cortex` with `raw.githubusercontent.com/xod-labs/cortex`. The release files did not change: a pinned SHA-256 still holds. Until you do, the old address redirects.

### You set `CORTEX_RELEASES_URL`

If it names `https://github.com/adorey/cortex/releases`, set it to `https://github.com/xod-labs/cortex/releases`, or unset it: that is the default from 1.2.2 on.

### You verify the attestations

From 1.2.2 on, the attestations name the new repository:

```bash
gh attestation verify ~/.cortex/bin/cortex --repo xod-labs/cortex
```

An attestation keeps the repository it was made in. Those of 1.0.0 to 1.2.1 name `adorey/cortex`, and GitHub lists them under the account `adorey`, not under the repository any more. Fetch the attestation first, then verify the file against it:

```bash
digest=$(sha256sum ~/.cortex/bin/cortex | cut -d' ' -f1)     # shasum -a 256 on macOS
gh api "users/adorey/attestations/sha256:$digest" --jq '.attestations[].bundle' > cortex.jsonl
gh attestation verify ~/.cortex/bin/cortex --bundle cortex.jsonl --repo adorey/cortex
```

## Questions

Open an issue on [xod-labs/cortex](https://github.com/xod-labs/cortex/issues). [ADR-008](adr/ADR-008-cortex-binary.md#9-amendments) records the move.
