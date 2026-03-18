# Capabilities — Loadable technical skills

> *"If I can understand these best practices in a dressing gown and without coffee, then the docs are good."* — Arthur Dent

## 🎯 What is this for?

Capabilities are **loadable technical skill modules**. Each file contains the universal best practices for a technology — independently of any project, role or personality.

A role declares the **capability categories** it needs. The Prompt Manager loads the corresponding files by cross-referencing with the stack declared in `project-context.md`.

**The difference from other layers:**

| Layer | Answers | Example |
|---|---|---|
| `roles/` | **WHAT** to do | "A lead backend structures, reviews, mentors" |
| `capabilities/` | **WHAT I KNOW HOW TO DO** | "In PHP: PSR-12, dependency injection..." |
| `personalities/` | **WHO** I am | "Hactar, methodical, elegant" |
| `project-context.md` | **WHERE** I work | "This project: Symfony 7.2, PHP 8.3, MySQL 8" |

## 📁 Structure

```
capabilities/
├── README.md                 # This file
├── languages/
│   ├── php.md                # PHP best practices
│   ├── typescript.md         # TypeScript best practices
│   └── ...
├── frameworks/
│   ├── symfony.md            # Symfony best practices
│   └── ...
├── infrastructure/
│   ├── docker.md             # Docker best practices
│   └── kubernetes.md         # Kubernetes best practices
├── databases/
│   └── mysql.md              # MySQL best practices
└── security/
    └── owasp.md              # OWASP Top 10 & best practices
```

## 🔄 Loading mechanism

### 1. The role declares its required categories

Each technical role has a `## 🔌 Capabilities` section listing the categories to load:

```markdown
## 🔌 Capabilities
- `languages/` → load the project's backend language
- `frameworks/` → load the project's backend framework
- `databases/` → load the project's DBMS
- `security/` → always load `security/owasp.md`
```

### 2. The Prompt Manager resolves the files

When a role is activated, the PM reads its `🔌 Capabilities` section, cross-references with the stack declared in `project-context.md`, and loads the corresponding files before producing the response.

**Example** — PHP/Symfony/MySQL project, `lead-backend` role:
```
Role declares : languages/, frameworks/, databases/, security/
project-context.md declares : PHP 8.3, Symfony 7.2, MySQL 8

PM loads:
  capabilities/languages/php.md
  capabilities/frameworks/symfony.md
  capabilities/databases/mysql.md
  capabilities/security/owasp.md
```

### Composing a complete agent

```
lead-backend.md (WHAT) + php.md + symfony.md (WHAT I KNOW HOW TO DO) + Hactar.md (WHO) + project-context.md (WHERE)
```

## ➕ Adding a capability

Create your file in the appropriate category and reference it in `project-context.md`. The PM will load it automatically if the active role declares the corresponding category.

## ✍️ Creating a new stack card

Each stack card follows this structure:

1. **Header** with version/date and official links
2. **Fundamental principles** (the non-negotiable rules)
3. **Recommended patterns** (with code examples)
4. **Anti-patterns** (what you should NEVER do, with examples)
5. **Quick checklist**

> *"Documentation is the developer's tea: nobody wants it until they desperately need it."* — Arthur Dent
