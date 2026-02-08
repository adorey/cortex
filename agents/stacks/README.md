# Stacks — Best Practices techniques

> *"Si je peux comprendre ces best practices en peignoir et sans café, alors la doc est bonne."* — Arthur Dent

## 🎯 À quoi ça sert ?

Les fiches stacks contiennent les **best practices universelles** d'une technologie. Elles ne sont liées ni à un projet, ni à un rôle, ni à une personnalité. Ce sont les règles du métier, point.

**La différence avec les autres couches :**

| Couche | Répond à | Exemple |
|---|---|---|
| `roles/` | **QUOI** faire | "Un lead backend structure, review, mentore" |
| `stacks/` | **COMMENT** le faire | "En PHP : PSR-12, injection de dépendances..." |
| `personalities/` | **QUI** tu es | "Hactar, méthodique, élégant" |
| `project-context.md` | **OÙ** tu travailles | "Ce projet : Symfony 7.2, PHP 8.3, MySQL 8" |

## 📁 Structure

```
stacks/
├── README.md                 # Ce fichier
├── languages/
│   ├── php.md                # Best practices PHP
│   ├── typescript.md         # Best practices TypeScript
│   └── ...
├── frameworks/
│   ├── symfony.md            # Best practices Symfony
│   └── ...
├── infrastructure/
│   ├── docker.md             # Best practices Docker
│   └── kubernetes.md         # Best practices Kubernetes
├── databases/
│   └── mysql.md              # Best practices MySQL
└── security/
    └── owasp.md              # OWASP Top 10 & best practices
```

## 🔧 Comment les utiliser

### Dans `project-context.md`

Référencez les stacks utilisées par votre projet :

```markdown
## Stack technique
- **Langage :** PHP 8.3 → voir `stacks/languages/php.md`
- **Framework :** Symfony 7.2 → voir `stacks/frameworks/symfony.md`
- **BDD :** MySQL 8 → voir `stacks/databases/mysql.md`
- **Infra :** Docker + K8s → voir `stacks/infrastructure/docker.md`, `stacks/infrastructure/kubernetes.md`
```

L'agent IA combinera automatiquement le rôle + les best practices de la stack + le contexte projet.

### Composition d'un agent

```
lead-backend.md (QUOI) + php.md + symfony.md (COMMENT) + Hactar.md (QUI) + project-context.md (OÙ)
```

## ✍️ Créer une nouvelle fiche stack

Chaque fiche stack suit cette structure :

1. **En-tête** avec version/date et liens officiels
2. **Principes fondamentaux** (les règles non négociables)
3. **Patterns recommandés** (avec exemples de code)
4. **Anti-patterns** (ce qu'il ne faut JAMAIS faire, avec exemples)
5. **Checklist** rapide

> *"La documentation, c'est le thé du développeur : personne n'en veut jusqu'à ce qu'il en ait désespérément besoin."* — Arthur Dent
