# What this changes

<!-- One or two sentences. What is different after this pull request? -->

Closes #

## Why

<!-- The problem, not the patch. If an ADR covers it, link it. -->

## Stack

<!-- Delete this section for a standalone pull request. -->

- **Targets:** `release/adr-NNN-slug`, or the phase branch below this one — never `main` for ADR work
- **Position:** phase N of ADR-NNN
- **Merge with:** a merge commit — **never squash or rebase** inside a stack

## How it was verified

<!-- Commands you ran and what they printed. "Tests pass" is less convincing than the count. -->

```bash
bash bin/check-english.sh
shellcheck --severity=warning setup.sh bin/*.sh
(cd runtime && python -m pytest -q)
```

## Checklist

- [ ] Commit subjects follow the [convention](../blob/main/CONTRIBUTING.md#commit-message-convention) — gitmoji + Conventional Commits, one line, no body, no trailer — with `#<issue>` before the subject for ADR work
- [ ] Tests cover the change — and a bug fix has a test that **fails without it**
- [ ] Docs updated if behaviour or setup changed (README, `docs/`, templates)
- [ ] An [ADR](../tree/main/docs/adr) was added or amended if this changes structure or contracts
- [ ] Everything added is in **English** — `bin/check-english.sh` passes
- [ ] Labelled like the issues it delivers — at least one `type:*`, plus `adr:NNN` and `phase:N` for ADR work
- [ ] No secret, real email, real organisation name or deployment-specific value added
- [ ] ADR work: every task delivered here is listed in `Closes`, and will be repeated in the release pull request — [why](../blob/main/docs/process/adr-implementation.md#6-commits-and-closing-keywords)
