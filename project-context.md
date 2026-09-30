<!-- @alias: cortex -->

# Technical context: Cortex

## 🏗️ Tech stack

### Stack principale
- **Source format:** Markdown (`.md`) — natively readable by any AI agent, with no special parsing
- **Configuration:** YAML front matter for metadata (where needed)
- **Tooling:** Python — the `cortex` command (`cli/`, built into a native binary) and `cortex-core` (`core/`); POSIX `sh` and PowerShell for the one-line install
- **No dependency for a host project** — the spec is static Markdown, the `cortex` binary embeds everything else

### Integration with AI tools
Cortex is **agnostic of the AI tool**. The entry instruction file depends on where it is used:

| Tool | Typical entry file |
|---|---|
| GitHub Copilot (VS Code) | `.github/copilot-instructions.md` |
| Cursor | `.cursorrules` ou `.cursor/rules/` |
| Claude Projects | The project's system instructions |
| ChatGPT Custom Instructions | Custom instructions |
| Other | Any instruction file the tool supports |

The content of that entry file is provided under `cortex/templates/`.

## 📁 Project structure

```
cortex/
├── agents/
│   ├── personalities/
│   │   └── h2g2/         ← Default theme (configurable — add other folders here)
│   ├── roles/            ← Mission cards per specialty (prompt-manager, architect…)
│   ├── capabilities/     ← Loadable technical skills (php, symfony, docker…)
│   └── workflows/        ← Multi-agent orchestration templates (generic)
├── assets/               ← Ressources statiques
├── docs/                 ← Documentation du framework
├── templates/            ← Project templates (entry instructions, project-context…)
├── cli/                  ← The `cortex` command: init, sync, validate
├── core/                 ← cortex-core, the cascade in code
├── runtime/              ← The engine: API, agentic loop
└── install.sh, install.ps1  ← The one-line install
```

## 📝 Code conventions

- **Format:** strict Markdown, one idea per section, concise headings
- **Naming:** kebab-case for files, PascalCase for character names
- **Separation of concerns:**
  - Personality cards → tone and style only
  - Role cards → mission et protocole technique uniquement
  - Capabilities → technical skills loaded on demand
- **Length:** files under 200 lines, so the context window is not saturated
- **Commits:** gitmoji + Conventional Commits, **single-line subject (≤72 chars), no body, never a `Co-Authored-By` trailer** (see [CONTRIBUTING.md](CONTRIBUTING.md))

## ⚡ Technical constraints

### Performance
- Short, focused files — each one must fit in a single read
- Load only the capabilities the host project's stack actually needs

### Security
- **No secret, credential or project data** in the Cortex repository
- Cortex is a generic public repository — everything in it must be reusable, unmodified, by any project
