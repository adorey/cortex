# Capabilities — Compétences techniques chargeables

> *"Si je peux comprendre ces best practices en peignoir et sans café, alors la doc est bonne."* — Arthur Dent

## 🎯 À quoi ça sert ?

Les capacités sont des **modules de compétences techniques chargeables**. Chaque fichier contient les best practices universelles d'une technologie — indépendamment de tout projet, rôle ou personnalité.

Un rôle déclare les **catégories de capacités** dont il a besoin. Le Prompt Manager charge les fichiers correspondants en croisant avec la stack déclarée dans `project-context.md`.

**La différence avec les autres couches :**

| Couche | Répond à | Exemple |
|---|---|---|
| `roles/` | **QUOI** faire | "Un lead backend structure, review, mentore" |
| `capabilities/` | **CE QUE JE SAIS FAIRE** | "En PHP : PSR-12, injection de dépendances..." |
| `personalities/` | **QUI** je suis | "Hactar, méthodique, élégant" |
| `project-context.md` | **OÙ** je travaille | "Ce projet : Symfony 7.2, PHP 8.3, MySQL 8" |

## 📁 Structure

```
capabilities/
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

## 🔄 Mécanisme de chargement

### 1. Le rôle déclare ses catégories requises

Chaque rôle technique possède une section `## 🔌 Capacités` qui liste les catégories à charger :

```markdown
## 🔌 Capacités
- `languages/` → charger le langage backend du projet
- `frameworks/` → charger le framework backend du projet
- `databases/` → charger le SGBD du projet
- `security/` → toujours charger `security/owasp.md`
```

### 2. Le Prompt Manager résout les fichiers

À l'activation d'un rôle, le PM lit sa section `🔌 Capacités`, croise avec la stack déclarée dans `project-context.md`, et charge les fichiers correspondants avant de produire la réponse.

**Exemple** — projet PHP/Symfony/MySQL, rôle `lead-backend` :
```
Rôle déclare : languages/, frameworks/, databases/, security/
project-context.md déclare : PHP 8.3, Symfony 7.2, MySQL 8

PM charge :
  capabilities/languages/php.md
  capabilities/frameworks/symfony.md
  capabilities/databases/mysql.md
  capabilities/security/owasp.md
```

### Composition d'un agent complet

```
lead-backend.md (QUOI) + php.md + symfony.md (CE QUE JE SAIS FAIRE) + Hactar.md (QUI) + project-context.md (OÙ)
```

## ➕ Ajouter une capacité

Créez votre fichier dans la catégorie appropriée et référencez-le dans `project-context.md`. Le PM le chargera automatiquement si le rôle actif déclare la catégorie correspondante.

## ✍️ Créer une nouvelle fiche stack

Chaque fiche stack suit cette structure :

1. **En-tête** avec version/date et liens officiels
2. **Principes fondamentaux** (les règles non négociables)
3. **Patterns recommandés** (avec exemples de code)
4. **Anti-patterns** (ce qu'il ne faut JAMAIS faire, avec exemples)
5. **Checklist** rapide

> *"La documentation, c'est le thé du développeur : personne n'en veut jusqu'à ce qu'il en ait désespérément besoin."* — Arthur Dent
