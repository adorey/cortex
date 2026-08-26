# Code comments — Best Practices

> Language-agnostic. The **mechanics** of a doc block for a given stack (PHPDoc, JSDoc/TSDoc,
> template comments) live in the matching `languages/` or `frameworks/` card. The **project's own
> conventions** — which language comments are written in, how tickets and decisions are referenced —
> belong in that project's `project-context.md`, not here.

No compiler, linter or test verifies a comment — and a comment that has drifted is worse than none,
because it is still trusted. The bar to write one: it says something the code cannot.

## 📐 Core principles

### 1. The *why*, not the *what*

Good naming is the first documentation. A comment that paraphrases the statement below it is noise —
delete it, or rename the thing it was compensating for.

```
❌ // increment the counter, then persist
❌ // required, >= 1, and dated whenever it changes    (sitting above the expression that says so)
✅ // Mirrors the server-side QuotaRequiredValidator: never block a save the API would accept.
```

### 2. Descriptive, not narrative

Describe what the code **is** and guarantees. Never narrate the change that introduced it, the ticket's
user journey, or the author's decision path — that belongs to git and to the tracker, and it becomes
false at the next commit while the code stays right.

**The six-month test:** would this sentence still be true *and* useful in six months, read by someone
who never saw the ticket? If not, it is a commit message in the wrong file.

```
❌ /** Step 2 of the journey described in the ticket. Without it the screen would be unreachable. */
❌ /** X and not Y because, when I tried Y, the save failed on some types … (four more lines) */
✅ /** The rate in force today: the most recent one whose effective date is not in the future. */
```

A compact technical reason **is** allowed — and wanted — when it is load-bearing: one sentence that
stops the next reader from *removing* something non-obvious. One sentence, not four.

### 3. Ambient density — below the rule, never above it

The project's convention sets the ceiling: what a comment must say, in which language, with which
references. The style of the file you are editing calibrates you only **underneath** that ceiling — a
file whose established style is trailing one-liners does not get five-line blocks. In review, a diff
whose comment volume approaches its code volume is a diff whose comments should be read first.

**A file that breaks the convention does not relax it.** Comments in the wrong language, doc blocks that
paraphrase, references that resolve to nothing: an existing violation is not a precedent. The comments
you **add or edit** follow the current rule, whatever the lines around them do.

**And you stop there.** Bringing the rest of the file into line is its own change — asked for, or
ticketed. Never a side effect of an unrelated diff: it buries the actual change and puts lines you had
no reason to touch into the blame.

### 4. One fact, one home

A fact belongs at the definition it is true of — not repeated at every call site. Three copies of the
same explanation is three things to keep in sync, and the next fix will land on only one of them. When
the invariant lives in a shared function, document it there and let the call sites read as plain code.

### 5. What actually earns a comment

- non-obvious business intent, invisible from the identifiers
- an invariant mirrored from another layer (server-side rule, API contract, schema quirk)
- a deliberate divergence — two nearby call sites doing the *same* check differently, on purpose
- a workaround for a third-party bug (name the library and the reason)
- an architecture decision — reference it (`ADR-00X §Y`) rather than re-arguing it
- a trade-off (performance, security) whose "obvious" simplification is wrong

### 6. Markers carry a reference

`TODO:` / `FIXME:` state the action and point at a tracked item. Without a reference it is a wish, and
wishes accumulate: nobody can tell a live one from a dead one.

### 7. No commented-out code

Git is the history. Dead code kept "just in case" survives every future search and misleads every future
reader.

## 🚫 Anti-patterns

```
❌ Restating a boolean expression in prose directly above it
❌ "Step N of the ticket's journey…" — narrating the specification
❌ Justifying the author's own implementation choice across several paragraphs
❌ The same explanation duplicated at three call sites instead of once at the definition
❌ Bare specification references (a rule number with no ticket/document to resolve it against)
❌ Commented-out code, and TODO/FIXME with no tracked reference
```

## ✅ Quick checklist

```
- [ ] Every added comment says something the code cannot
- [ ] Still true and useful in six months, to a reader who never saw the ticket
- [ ] No narration of the change, no multi-paragraph self-justification
- [ ] Density under the project's rule — a non-compliant file is not a licence
- [ ] Each fact documented once, at its definition
- [ ] References resolvable (ADR / ticket / library), never a bare rule number
- [ ] No commented-out code; markers carry a reference
```

## 🔗 Interactions

- **Lead Backend / Lead Frontend** → apply the card on every diff; the per-language doc-block mechanics
  are in their stack's `languages/` and `frameworks/` cards.
- **Architect** → owns the decisions the code references.
- **Tech Writer** → what a comment must not carry (rationale, history, walkthroughs) is what the docs
  and the ADRs exist for.
