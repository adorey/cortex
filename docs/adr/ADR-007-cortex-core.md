# ADR-007 — Cortex Core: unified cascade resolution

- **Status:** Accepted
- **Date:** 2026-09-23 (proposed) · 2026-09-23 (accepted)
- **Authors:** Cortex maintainers (initiated by the maintainer, drafted by @Oolon)
- **Affects:** a new `core/` package (`cortex_core`), `runtime/cortex_runtime/resolver.py` and `context.py`, `bin/validate-overlays.sh`, `runtime/tests/test_parity.py` and `test_firewall.py`, `deploy/Dockerfile`, CI, the contributor prerequisites
- **Relates to:** [ADR-001](ADR-001-layered-overrides.md) — refines §3.1, the base locator only; the cascade and its merge semantics are untouched · [ADR-002](ADR-002-cortex-runtime.md) §3.1 and §3.4 — the executable resolver and its `root` binding · [ADR-006](ADR-006-workspace-shareable-repo.md) — the team tier the runtime does not read yet · roadmap epic [#36](https://github.com/adorey/cortex/issues/36)

---

## 1. Context

The ADR-001 cascade is implemented **twice in code**, and a third time in prose:

| Implementation | Language | Used by |
|---|---|---|
| `runtime/cortex_runtime/resolver.py` and `context.py` | Python | the runtime, to assemble a system prompt |
| `bin/validate-overlays.sh` | Bash | host projects and CI, to validate overlays |
| the bootstrap templates and `agents/roles/prompt-manager.md` | natural language | the LLM, which resolves the cascade itself at boot |

The two code implementations are kept "behaviourally identical" by hand, with `runtime/tests/test_parity.py` as the guard. Three facts show that the arrangement no longer holds.

1. **They already disagree, and the guard cannot see it.** A file at a base path that lacks the `<!-- OVERLAY -->` header is a *custom addition* to the validator, which skips it — and an overlay to the resolver, which only checks that the file exists and stacks it onto the base. `test_parity.py` compares `✓` and `✗` verdicts only; the validator reports that case as `ℹ`, so the test is blind to it.
2. **The base location is hard-coded four times.** `root / "cortex" / "agents"` appears in `resolve_layer`, `find_role_relpath`, `find_workflow_relpath` and in the capability catalog of `context.py`. The base is assumed to be a submodule at `{project}/cortex/`. The next step of the roadmap — a globally installed Cortex, ADR-008 — needs it to live elsewhere; and Cortex cannot resolve its own repository today, where the base *is* the root.
3. **The runtime drifted from the spec.** ADR-006 added a team tier, `{workspace_root}/agents/project-context.md`; the runtime's `read_project_context` still reads only the root and service files.

Each client on the roadmap — a `cortex` CLI, IDE extensions — would add one more implementation. The count has to go down before it goes up.

## 2. Decision

Extract **cortex-core**: one library that owns everything Cortex computes from the spec — cascade resolution, merge semantics, role, workflow and character lookup, the capability catalog, prompt assembly and overlay validation — **parameterised by a `base_root`**.

- The runtime and the validator's entry point consume it; neither keeps a copy.
- The ADR-001 cascade and its merge semantics are unchanged. Only the **locator** of the base generalises.
- `base_root` defaults to `{project_root}/cortex`, so the extraction changes **no behaviour**. The two drifts listed above are fixed afterwards, deliberately, in a phase of their own — once parity is proven.

## 3. Detailed contract

### 3.1 Two roots instead of one

```text
before:  base    = {root}/cortex/agents/{layer}/{file}
after:   base    = {base_root}/agents/{layer}/{file}              # base_root defaults to {project_root}/cortex
         overlay = {project_root}/agents/{layer}/{file}           # unchanged
         service = {project_root}/{service}/agents/{layer}/{file} # unchanged
```

Setting `base_root = {project_root}` resolves a repository that is its own base — Cortex itself. The base and the workspace tier are then **the same directory**: a file found there is read once, as the base, never stacked onto itself. Setting `base_root` to an installation directory is ADR-008's concern.

### 3.2 What cortex-core owns — and what it does not

| Owned by cortex-core | Stays where it is |
|---|---|
| Resolution — `resolve_layer` | Run orchestration, state, the API, the security gate — the runtime |
| Merge semantics — `semantic_for`, `read_resolved` | The `cortex` CLI — ADR-008 |
| Lookups — role, workflow, character | Prompt-side resolution by the LLM — ADR-008's materialized mode makes it unnecessary |
| The capability catalog | |
| Prompt assembly — `layers_for`, `build_system_prompt` | |
| Overlay validation — ADR-001 Tier 1 and Tier 2, and the discovery of overlay roots | |

Prompt assembly belongs to the core because every client needs it: the runtime today, `cortex resolve` tomorrow.

### 3.3 The package

- `core/`, imported as `cortex_core`, distributed as `cortex-core` — the same shape as `runtime/`.
- **No third-party dependency**, and `requires-python >= 3.9` — deliberately lower than the runtime's 3.11: the core must run from source on a host machine, with no install step. 3.9 is the Python such machines already have: Apple's Command Line Tools install Python 3.9.6 as `/usr/bin/python3` (macOS 15 included), and RHEL 9 and its rebuilds ship 3.9 as their system Python, maintained by the distribution after upstream's end of life in October 2025. Raising the floor drops those machines — until the native binary of ADR-008 makes the question moot.
- **Dependency direction:** the runtime imports the core; the core never imports the runtime. A test enforces it, and the ADR-002 firewall test is extended so that spec Markdown references neither.

### 3.4 The `Base:` header stays a logical identifier

Overlay headers keep `Base: cortex/agents/{layer}/{path}`. The validator resolves it as `{base_root}/agents/{layer}/{path}`. No overlay in any host project has to be rewritten.

### 3.5 The validator's entry point

`bin/validate-overlays.sh` stays the command host projects and CI run, with the same options (`--service`, `--strict`, `--help`), the same output and the same exit codes (`0`, `1`, `2`). It becomes a thin shim over `python3 -m cortex_core.validate`, run from the `core/` directory of the Cortex checkout — there is nothing to install.

If no Python 3.9 or later is found, the shim exits `2` with a message naming the requirement. The module entry point is internal: it is not the `cortex` CLI, which ADR-008 introduces.

### 3.6 Behaviour changes — phase 4 only

Two, each documented when it lands:

- **`MISSING_HEADER`** — a file at a base path without an `<!-- OVERLAY -->` header is reported as a warning, an error under `--strict`: the resolver stacks it, so it *is* an overlay. A file at a path where no base exists remains a custom addition.
- **The team tier** — the runtime reads `{workspace_root}/agents/project-context.md` before the root file, each labelled by scope, in the aggregation order of ADR-006 §3.3.

## 4. Phases

Execution order: **1 → 2 → 3 → 4**. Phases 1 to 3 gate the ADR's release; phase 4 does not.

### Phase 1 — The resolver, extracted and parameterised

Create `core/` and move into it the resolution, the merge semantics, the lookups, the capability catalog and the prompt assembly, parameterised by `base_root`. The runtime consumes the core and keeps its public API; the runtime image ships the core. The Bash validator is not touched.

Acceptance criteria:

- `git grep -n '"cortex"' runtime/cortex_runtime/` returns nothing
- the runtime test suite passes with no test modified — `test_parity.py` included
- `docker build -f deploy/Dockerfile .` succeeds, and the container answers `GET /health`
- a test fails when any `cortex_core` module imports `cortex_runtime`
- resolving `roles/engineering/lead-backend.md` with `base_root` and `project_root` both set to the Cortex repository returns the repository's own file **once**, and its resolved content equals that file

### Phase 2 — The validator, at parity

First freeze the Bash validator's behaviour: one fixture per verdict — `✓`, `ℹ`, every error code and every warning code — with its exact output and exit code captured, with and without `--strict`, and once with `--service`. Then port Tier 1, Tier 2, the discovery of overlay roots and the options to `cortex_core.validate`. The Bash script remains the entry point and is not modified.

Acceptance criteria:

- `python -m cortex_core.validate` reproduces every captured output byte for byte, the absolute path of the temporary directory aside
- it returns the captured exit code for every fixture

### Phase 3 — One implementation

`bin/validate-overlays.sh` becomes the shim of §3.5. Its validation logic and `test_parity.py` are deleted; the outputs captured in phase 2 now run through the shim. The Python 3.9 prerequisite is documented.

Acceptance criteria:

- the CI scaffold job passes in both modes, submodule and workspace, without modification
- `grep -c report_error bin/validate-overlays.sh` returns `0`
- every output captured in phase 2 is reproduced through the shim
- with no Python 3.9 or later available, the shim exits `2` and names the requirement

### Phase 4 — The two drifts, closed deliberately

The behaviour changes of §3.6.

Acceptance criteria:

- a file without a header at `agents/roles/engineering/lead-backend.md` produces `MISSING_HEADER` — a warning, and an error under `--strict` — while a file without a header at a path with no base still reports `ℹ`
- for a workspace carrying both files, the runtime's project context contains `agents/project-context.md`, labelled, before the root `project-context.md`, labelled

## 5. Consequences

### Positive

- **One implementation of the cascade in code.** A divergence becomes impossible instead of guarded against.
- **The base is locatable.** ADR-008 can point `base_root` at a global installation without touching resolution again.
- **Cortex resolves itself** — an end-to-end test of the cascade on the one repository guaranteed to exist.
- **Every future client** — the CLI, the IDE extensions — imports the core instead of re-implementing it.

### Negative

- **Host projects need Python 3.9 or later to validate overlays**, where Bash was enough. It lasts until ADR-008 ships a native binary that embeds the core. Most development machines and CI runners have it, and the shim says so plainly when they do not.
- **One more package** to build, test and ship — the runtime image installs three local packages instead of two.
- **The outputs captured in phase 2** become fixtures to maintain: a deliberate change to the validator's wording now edits them too.

### Neutral

- The prompt-side cascade, which the LLM follows from the bootstrap templates, is unchanged — it stays the third implementation until ADR-008.
- ADR-001 remains `Accepted`: this ADR refines its locator, it does not supersede its contract.

## 6. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Keep two implementations and a stronger parity test** | The parity test already missed a divergence, and each new client would add an implementation — and a guard for every pair. |
| **Make Bash the single implementation** | The runtime, the CLI and the IDE extensions cannot import a shell script. |
| **Leave the validator alone until ADR-008's native binary** | The duplication would survive a whole ADR longer, and ADR-008 would be built on two resolvers. |
| **Put the core inside the runtime package** (`cortex_runtime.core`) | A CLI or an IDE extension would then pull the whole runtime and its web framework to resolve one file. |
| **Fix the two drifts while extracting** | A refactor that also changes behaviour cannot prove that it is a refactor. |

## 7. Follow-ups (out of scope for this ADR)

1. **ADR-008** ([#37](https://github.com/adorey/cortex/issues/37)) — `$CORTEX_HOME` as `base_root`, `cortex.toml`, the native binary that removes the Python prerequisite, and the materialized mode that makes the prompt-side cascade unnecessary.
2. The Tier 3 validations ADR-001 planned (verbatim duplicates, recap statistics) — to be written once, in the core.

## 8. References

- [ADR-001 — Layered overrides](ADR-001-layered-overrides.md) — the cascade whose locator this ADR generalises
- [ADR-002 — Cortex Runtime](ADR-002-cortex-runtime.md) — §3.1, the executable resolver; §3.4, the `root` binding
- [ADR-006 — Team and developer context](ADR-006-workspace-shareable-repo.md) — the team tier of §3.6
- [docs/process/adr-implementation.md](../process/adr-implementation.md) — how the phases above are delivered
- Roadmap epic [#36](https://github.com/adorey/cortex/issues/36)

## 9. Amendments

### Phase 1 — the firewall, extended from the core's side

§3.3 extends the ADR-002 firewall test so that spec Markdown references neither the runtime nor the core. That test is `runtime/tests/test_firewall.py`, and phase 1 must pass with no runtime test modified. The core's tokens are therefore guarded by a test of the core's own, `core/tests/test_boundaries.py`, which also enforces the dependency direction; the runtime's test keeps guarding the runtime's. The guarantee is the one §3.3 asks for, held by two files instead of one.

### Phase 2 — where the port parts from the script, on purpose

- **What sits behind a symbolic link is validated.** The script's `find -P … -type f` entered no link: with `agents/roles` a link to a shared directory it checked nothing, and it skipped a subdirectory or an overlay file that was a link — while the resolver reads through every one of them. The port validates what the resolver reads, as `find -L` would, and enters a directory reached twice — a link loop — once; tests pin all four. Discovering services still follows no link.
- **The C locale, whatever the machine's.** The script's `grep` and `sed` followed the locale they ran in: under a UTF-8 one — CI runners' — `[[:space:]]` also matched Unicode spaces, so a header value ending in, say, U+2003 was trimmed there and not in the C locale. The port reads bytes and ASCII character classes, as the C locale does, on every machine; the captured outputs are measured with the script under `LC_ALL=C` to match.
- **Two differences left as they are.** A file name holding a newline was two names to the script, which read `find`'s output line by line — two files that do not exist, each reported — and is one name to the port. Past 10,000 entries in one directory, GNU `find` lists them in inode order on the file systems where that is faster, where the port keeps the directory's own order: the report lists the same files, in another order.

### Phase 3 — the shim imports the core, isolated

§3.5 describes the shim as running `python3 -m cortex_core.validate` from the checkout's `core/` directory. Run that way, Python trusts two things the project under validation can control. The first implementation ran the module from the caller's working directory, with `core/` added to `PYTHONPATH`: the working directory went to the head of `sys.path`, so validating a project whose root holds, say, an `fnmatch.py` executed that file — in CI included. Run from `core/` as §3.5 says, the working directory is harmless, but `PYTHONPATH` still precedes the standard library: a `PYTHONPATH` pointing at the project — common in CI — runs its `fnmatch.py` all the same, and a Python started without isolation also imports a `sitecustomize.py` it finds there. The Bash implementation had no such exposure.

The shim therefore starts Python under `-I` — isolated mode: neither the working directory nor `PYTHONPATH` lands on `sys.path`, and no `sitecustomize` or user site-packages is loaded — for its version probe as for the run. It then puts the checkout's `core/` first on `sys.path` and imports `cortex_core.validate` from there, so the validator applies the resolver's own rules — which layer replaces, which file cannot be overridden — instead of restating them: the one implementation §2 decides. The core imports the standard library only — a test holds it to that — so there is still nothing to install. One test changes the resolver's rule and watches the validator's verdict follow; another validates a project carrying hostile `fnmatch.py`, `re.py`, `typing.py`, `enum.py`, `pathlib.py`, `sitecustomize.py` and `cortex_core/` files, with `PYTHONPATH` pointing at it. Options, output and exit codes are unchanged.

### Phase 4 — a third drift, and how the team tier is labelled

Freezing the Bash validator in phase 2 surfaced a third drift of the kind §3.6 lists. With the `Base:`, `Scope:` or `Semantic:` key **absent** — not empty — the script aborted: `grep` matched nothing, `pipefail` failed the assignment and `set -e` exited `1` before any verdict, without naming the file or printing the summary. `MISSING_FIELD` was only reachable with the key present and its value empty. Phase 2 reproduced it, as a parity phase must; phase 4 reports an absent key as `MISSING_FIELD` and goes on to the next file. It is tracked as #81, a task added to phase 4 during implementation.

§3.6 asks for the two workspace context tiers to be "labelled by scope". The runtime labels them when **both** exist: with a single tier there is no scope to tell apart, so a workspace without a team tier sees its context unchanged.

### Phase 4 — what the port kept of the script, fixed

Phase 2 reproduced three behaviours of the Bash script as they were — a parity phase is no place to fix them — and #79 listed them. Once phase 3 had deleted the script, the maintainer asked for them to be fixed in phase 4, beside the drifts of §3.6:

- **Paths come from the root being scanned** (#84). The script cut absolute paths at their first `/agents/` and skipped every path matching `*/cortex/*`: a project inside a directory named `agents` failed every overlay with `PATH_MIRROR`, and one inside a directory named `cortex` had none of its services checked — exit `0`, under `--strict` too. It also told a service overlay from a workspace one by counting slashes, which missed a service overlay with no category level. The validator now works from the root it scans, and skips the base by its location, whatever it is called, as well as any directory named `cortex` or `.git` below the project root. ADR-001 §3.4's *file is in a known layer directory* holds by construction, since discovery walks the four layer directories only: `UNKNOWN_LAYER`, which only the first of these bugs could produce, is gone.
- **What was read is printed as it was read** (#85). The script passed header values and file names through `echo -e`, so an overlay could write terminal control sequences to the console; control characters are now shown escaped — `\x1b` for ESC. The workspace's section is headed `── Scope: . ──`, as the script meant to and never did.

Both change the captured outputs, re-captured and reviewed case by case.

### Phase 4 — found in review

- **The base is no overlay of itself.** Called with the project root as the base — Cortex validating itself, the case ADR-008 opens — the validator scanned the base's own files as workspace overlays and, with `MISSING_HEADER`, reported every one of them. A project root that is the base is no workspace tier: its files are the base, read once, as the resolver reads them (§3.1).
- **`characters.md` without a header is still not overridable.** Once `MISSING_HEADER` existed, removing the header from an overlay of `personalities/{theme}/characters.md` turned the `NON_OVERRIDABLE` error into a warning — and its advice, *add the header*, led back to the error. The resolver never stacks that file, header or not, so a headerless copy at the path of a base is `NON_OVERRIDABLE` too. A theme of the project's own, with no base of that name, stays a custom addition, as `docs/creating-a-theme.md` allows.
- **A README is documentation.** A host project's `agents/roles/README.md` sits at the path of the base's own, so `MISSING_HEADER` reported it — and failed `--strict` over an index page. The resolver never reads a README and the catalog leaves them out; the validator now shares the catalog's rule, in any case.
- **The project context reaches the agent** (#87). `read_project_context` served `derive_capabilities` only: the context — the file meant to give an agent the whole project — never reached the model. It now closes the system prompt under `# Project context`, after identity, protocol and capabilities; with no context file the prompt is what it was. Once in the prompt the tiers must be told apart, so each — the service's included — is labelled as soon as there are two or more, which widens the rule this section gave for the team tier.
- **The overview and the workspace's services reach the agent too** (#88). In the editor the Prompt Manager reads the overviews, then the contexts, then the active service's own, and knows the services by their `@alias`. The runtime's agent now sees the same: `# Project overview`, then `# Workspace services` — one line per service, alias, folder, title, the run's own marked — then `# Project context`. Service discovery, the validator's until then, moves to `cortex_core.workspace`, so the overlay roots and the index are found by one implementation.

