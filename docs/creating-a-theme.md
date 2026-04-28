# Creating a Personality Theme

> *"If I can understand this guide in my dressing gown and without coffee, then the documentation is good."* — Arthur Dent
>
> This guide explains how to create a custom personality theme for your Cortex team.

## 🎯 What is a theme?

A theme is a **personality layer** that sits on top of the technical roles and capabilities to give a tone, style and identity to your AI agents. It is purely cosmetic and cultural: it does not affect technical skills or stack best practices.

**Examples:**
- `h2g2` — The Hitchhiker's Guide to the Galaxy (British humour, SF)
- `star-wars` — Star Wars (Jedi wisdom, imperial rigour…)
- `corporate` — Neutral professional (no character, formal tone)
- `lotr` — The Lord of the Rings (elven wisdom, dwarven robustness…)

> **Overlay vs theme fork — when to choose which?**
>
> - You want to **add** project-specific quotes, traits, or flavor to an existing character → use an [overlay](extending-layers.md) on `personalities/{theme}/{Character}.md`.
> - You want to **change which character plays which role** (e.g. assign a different persona to the DBA role) → fork the theme (this guide). The role↔character mapping in `characters.md` is **not** overridable.
> - You want a **completely different universe** (Star Wars instead of H2G2) → create a new theme (this guide).

## 📁 Theme structure

```
cortex/agents/personalities/{theme-name}/
├── README.md         # Theme description and instructions
├── theme.md          # Global tone, communication rules, narrative context
├── characters.md     # Role → character mapping + traits + quotes
└── {Character}.md    # (optional) Individual card per character
```

> **Note on roles:** Cortex roles are organised by category in `roles/`.
> Paths in character cards follow the pattern `../../roles/{category}/{role}.md`.
> Available categories: `engineering/`, `product/`, `security-compliance/`, `data/`, `communication/`.

## 📝 Step by step

### 1. Create the folder

```bash
mkdir -p cortex/agents/personalities/my-theme
```

### 2. Create `theme.md`

This file defines the global rules of the theme. It is read by the AI to apply the tone.

```markdown
# [Name] Theme — Rules & Tone

<!-- SYSTEM PROMPT ADDON — PERSONALITY LAYER
When this theme is active, ALL responses must:
1. Adopt the tone of the character assigned to the role (see characters.md)
2. Start with the character's signature quote
3. Use analogies and references to [universe] when natural
4. NEVER sacrifice technical quality for style
-->

## 🎭 Theme identity

**Source:** [Original work]
**Tone:** [Tone description: humour, serious, epic…]
**Motto:** [Iconic phrase]

## 📏 Rules

### Do
- [Rule 1]
- [Rule 2]

### Don't
- [Anti-pattern 1]
- [Anti-pattern 2]
```

### 3. Create `characters.md`

This file maps each Cortex role to a character from your universe.

```markdown
# [Name] Theme — Characters

## 👥 Mapping table

| Role (`roles/`) | Character | Alias | Card | Traits | Signature quote |
|---|---|---|---|---|---|
| `prompt-manager` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `architect` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `lead-backend` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `lead-frontend` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `security-engineer` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `qa-automation` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `platform-engineer` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `product-owner` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `tech-writer` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `data-analyst` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `compliance-officer` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `dba` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `business-analyst` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `performance-engineer` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
| `consultant-platform` | [Character] | @Alias | [📄](Character.md) | [Traits] | *"Quote"* |
```

> **Tip:** The `Card` column is optional but recommended for rich characters.
> If you create individual cards, see step 3.5 below.

### 3.5 (Optional) Create individual character cards

For rich characters, create one `.md` file per character:

```markdown
# [Character]

<!-- PERSONALITY PROMPT
Adopt the personality of [Character].
Your technical role is defined in `../../roles/{category}/{role}.md`.
Project context is in `../../project-overview.md` (vision & business) and `../../project-context.md` (stack & conventions).
-->

> "[Signature quote]" - [Character]

## 👤 Character
[Biography / universe context]

## 🎭 Communication style
- **Tone:** [description]
- **Habit:** [typical behaviour]
```

### 4. Create `README.md`

```markdown
# [Name] Theme — [Universe]

> [Iconic quote]

## About
[Short description of the theme]

## Usage
Activate this theme with:
\`\`\`bash
./cortex/setup.sh --theme my-theme
\`\`\`
```

### 5. Activate the theme

**At install time:**

```bash
./cortex/setup.sh --theme my-theme
```

This regenerates the bootstrap file for your AI tool (e.g. `.github/copilot-instructions.md` for Copilot, `CLAUDE.md` for Claude Code, etc.) and writes `my-theme` to `agents/personalities/.active-theme`.

**Switch theme post-install (no setup re-run needed):**

The active theme is stored in a single marker file **inside cortex**:

```bash
echo "my-theme" > cortex/agents/personalities/.active-theme
```

The PM reads this file at the start of every conversation. The new theme takes effect immediately on the next prompt — no regeneration of `CLAUDE.md` / `copilot-instructions.md` required.

**Disable personality entirely:**

```bash
echo "none" > cortex/agents/personalities/.active-theme
```

(Equivalent to having run `./cortex/setup.sh --no-personality`.)

> **Why is the marker inside cortex but gitignored?**
>
> The marker is a **cortex concern** — it tells the framework which theme to load. So it lives in `cortex/agents/personalities/.active-theme`. But cortex's own [`.gitignore`](../.gitignore) excludes it, because the choice is **per-developer** (like editor color scheme), not framework state. Alice can prefer H2G2 humor while Bob runs in no-personality mode — neither pollutes git diffs.
>
> If your team explicitly *wants* a shared default theme, remove the line from `cortex/.gitignore` and commit the marker. (You'll need to push that change to your fork of cortex if you maintain one.)

## 🎭 Where can custom themes live?

A custom theme can live in **any** of these places (the cascade resolves at boot):

| Location | When to use |
|---|---|
| `cortex/agents/personalities/{theme}/` | You contribute the theme upstream (PR to cortex) |
| `agents/personalities/{theme}/` (project root) | Single-project mode — theme is yours, kept in your project repo |
| `{workspace_root}/agents/personalities/{theme}/` | Workspace mode — theme shared across all services in your workspace |
| `{service}/agents/personalities/{theme}/` | Workspace mode — theme specific to one service |

A theme that exists **only** in your overlay tree (no cortex base) is fully supported. The PM walks the cascade and finds the files wherever they are. You don't need to PR your theme upstream just to use it.

When you add a custom theme:
- Set its name in the marker: `echo "my-theme" > cortex/agents/personalities/.active-theme`
- Add `theme.md` and `characters.md` (and optional character cards) at one of the cascade paths above
- No `<!-- OVERLAY -->` header is needed for fully custom themes — that header is only for **extending** an existing cortex theme

## 💡 Tips

### Choosing the right characters

| Role | Look for a character who... |
|---|---|
| `prompt-manager` | Communicates clearly, organises, synthesises |
| `architect` | Plans, designs, has the big picture |
| `lead-backend` | Is methodical, rigorous, technical |
| `lead-frontend` | Is creative, user-oriented, accessible |
| `security-engineer` | Is cautious, suspicious, exhaustive |
| `qa-automation` | Is rigorous, leaves nothing to chance |
| `platform-engineer` | Is pragmatic, resourceful, solution-oriented |
| `product-owner` | Is visionary, decisive, impact-driven |
| `tech-writer` | Is pedagogical, clear, patient |
| `data-analyst` | Is curious, analytical, finds patterns |
| `compliance-officer` | Is conscientious, thoughtful, ethical |
| `dba` | Is orderly, precise, procedural |
| `business-analyst` | Asks the right questions, bridges worlds |
| `performance-engineer` | Is patient, analytical, seeks the optimal |
| `consultant-platform` | Has perspective, is experienced, gives frank advice |

### Keeping the balance

- Personality should **enrich** communication, not complicate it
- Technical responses remain the **absolute priority**
- `capabilities/` and `roles/` cards are never affected by the theme
- When in doubt between humour and clarity, **clarity always wins**
- A theme that's too heavy becomes tiring: stay **subtle**

> *"Documentation is like the developer's tea: nobody wants it until they desperately need it."* — Arthur Dent

## 🔧 Example: Star Wars theme (sketch)

| Role | Character | Traits |
|---|---|---|
| `architect` | Yoda | Wise, speaks in metaphors, long-term vision |
| `lead-backend` | Obi-Wan Kenobi | Disciplined, mentor, master of the Force (of code) |
| `security-engineer` | Darth Vader | Authoritative, tolerates no flaws, exhaustive |
| `product-owner` | Leia Organa | Born leader, strategist, pragmatic |
| `platform-engineer` | Han Solo | Resourceful, pragmatic, "it'll work" |
| `qa-automation` | C-3PO | Meticulous, anxious, knows all the protocols |
| `dba` | R2-D2 | Efficient, reliable, communicates in beeps (data) |
