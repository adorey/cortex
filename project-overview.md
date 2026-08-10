<!-- @alias: cortex -->

# Overview: Cortex

## 📋 General information

**Name:** Cortex
**Description:** A tool-agnostic AI agent orchestration framework — it provides the roles, personalities, workflows and capabilities that let an AI agent operate as a multidisciplinary expert team on any project.
**Business domain:** Developer Tooling / AI-assisted development
**Status:** Active — public, reusable framework

## 🎯 Main actors

| Actor | Description |
|-------|-------------|
| User | Anyone interacting with an AI agent through prompts |
| AI agent | Reads the Cortex context files and adopts the matching role/personality |

## 🔄 Key business processes

### Bootstrap de conversation
- The agent reads the workspace instruction file (e.g. copilot-instructions.md, .cursorrules, AGENTS.md, or any other file the AI tool supports)
- It loads the host project's project-overview.md and project-context.md
- It identifies the active personality theme (H2G2 by default, but configurable) and adopts the prompt-manager role

### Reformulation & dispatch — le coeur du Prompt Manager
This is the framework's **most critical** step:
1. **Analyse** the incoming prompt: clarity, completeness, potential ambiguities
2. **Reframe** the request to make it precise, complete and unambiguous
3. **Identify** the expert role best placed to answer (through characters.md)
4. **Load** the role card + the personality card + the relevant capabilities
5. **Dispatch** to that expert and produce the answer

Without that reframing step, every following exchange is built on unstable foundations.

### Activation d'un workflow
- Looks first in the host project's agents/workflows/ (higher priority)
- Then in cortex/agents/workflows/ (generic workflows)
- Orchestrates the steps and the agents involved

## 📏 Important business rules

- **Tool agnosticism:** Cortex is independent of any tool or IDE. The entry instruction file is specific to each integration (GitHub Copilot, Cursor, Claude, ChatGPT custom instructions…)
- **Configurable theme:** H2G2 is the personality theme shipped by default. Any other theme can be created under personalities/ and activated
- **Capabilities on demand:** loaded only according to the host project's stack, as declared in project-context.md
- **Project workflows over generic ones:** the project context always wins
- **Generic public repository:** no project name and no business data may appear in Cortex itself

## 📚 Resources & documentation

- **Documentation :** cortex/docs/ (getting-started.md, creating-a-theme.md)
- **Templates:** cortex/templates/ (entry instructions, project-context, project-overview…)
