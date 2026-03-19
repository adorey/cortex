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

```bash
./cortex/setup.sh --theme my-theme
```

This will update `.github/copilot-instructions.md` to point to your theme.

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
