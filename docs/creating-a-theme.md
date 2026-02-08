# Créer un thème de personnalité

> Ce guide explique comment créer un thème de personnalité custom pour votre équipe Cortex.

## 🎯 Qu'est-ce qu'un thème ?

Un thème est une **couche de personnalité** qui se superpose aux rôles techniques pour donner un ton, un style et une identité à vos agents IA. C'est purement cosmétique et culturel : ça n'affecte pas les compétences techniques.

**Exemples :**
- `h2g2` — Le Guide du voyageur galactique (humour british, SF)
- `star-wars` — Star Wars (sagesse Jedi, rigueur impériale…)
- `corporate` — Professionnel neutre (pas de personnage, ton formel)
- `lotr` — Le Seigneur des Anneaux (sagesse elfique, robustesse naine…)

## 📁 Structure d'un thème

```
cortex/agents/personalities/{nom-du-theme}/
├── README.md         # Description du thème et instructions
├── theme.md          # Ton global, règles de communication, contexte narratif
└── characters.md     # Mapping rôle → personnage + traits + citations
```

## 📝 Étape par étape

### 1. Créer le dossier

```bash
mkdir -p cortex/agents/personalities/mon-theme
```

### 2. Créer `theme.md`

Ce fichier définit les règles globales du thème. Il est lu par l'IA pour appliquer le ton.

```markdown
# Thème [Nom] — Règles & Ton

<!-- SYSTEM PROMPT ADDON — PERSONALITY LAYER
Quand ce thème est actif, TOUTES les réponses doivent :
1. Adopter le ton du personnage assigné au rôle (voir characters.md)
2. Commencer par une citation signature du personnage
3. Utiliser des analogies et références à [univers] quand c'est naturel
4. NE JAMAIS sacrifier la qualité technique pour le style
-->

## 🎭 Identité du thème

**Source :** [Œuvre d'origine]
**Ton :** [Description du ton : humour, sérieux, épique…]
**Motto :** [Phrase emblématique]

## 📏 Règles

### À faire
- [Règle 1]
- [Règle 2]

### À ne pas faire
- [Anti-pattern 1]
- [Anti-pattern 2]
```

### 3. Créer `characters.md`

Ce fichier mappe chaque rôle Cortex à un personnage de votre univers.

```markdown
# Thème [Nom] — Personnages

## 👥 Table de correspondance

| Rôle (`roles/`) | Personnage | Alias | Traits | Citation signature |
|---|---|---|---|---|
| `prompt-manager` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `architect` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `lead-backend` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `lead-frontend` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `security-engineer` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `qa-automation` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `platform-engineer` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `product-owner` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `tech-writer` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `data-analyst` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `compliance-officer` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `dba` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `business-analyst` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `performance-engineer` | [Personnage] | @Alias | [Traits] | *"Citation"* |
| `consultant-platform` | [Personnage] | @Alias | [Traits] | *"Citation"* |
```

### 4. Créer `README.md`

```markdown
# Thème [Nom] — [Univers]

> [Citation emblématique]

## À propos
[Description courte du thème]

## Utilisation
Activez ce thème avec :
\`\`\`bash
./cortex/setup.sh --theme mon-theme
\`\`\`
```

### 5. Activer le thème

```bash
./cortex/setup.sh --theme mon-theme
```

Cela mettra à jour le `.github/copilot-instructions.md` pour pointer vers votre thème.

## 💡 Conseils

### Choisir les bons personnages

| Rôle | Cherchez un personnage qui... |
|---|---|
| `prompt-manager` | Communique clairement, organize, synthétise |
| `architect` | Planifie, conçoit, a une vision d'ensemble |
| `lead-backend` | Est méthodique, rigoureux, technique |
| `lead-frontend` | Est créatif, orienté utilisateur, accessible |
| `security-engineer` | Est prudent, méfiant, exhaustif |
| `qa-automation` | Est rigoureux, ne laisse rien au hasard |
| `platform-engineer` | Est pragmatique, débrouillard, orienté solutions |
| `product-owner` | Est visionnaire, décisif, orienté impact |
| `tech-writer` | Est pédagogue, clair, patient |
| `data-analyst` | Est curieux, analytique, cherche les patterns |
| `compliance-officer` | Est consciencieux, réfléchi, éthique |
| `dba` | Est ordonné, précis, procédurier |
| `business-analyst` | Pose les bonnes questions, fait le pont entre mondes |
| `performance-engineer` | Est patient, analytique, cherche l'optimal |
| `consultant-platform` | A du recul, est expérimenté, donne des conseils francs |

### Garder l'équilibre

- La personnalité doit **enrichir** la communication, pas la compliquer
- Les réponses techniques restent la **priorité absolue**
- En cas de doute entre humour et clarté, **la clarté gagne toujours**
- Un thème trop lourd fatigue : restez **subtil**

## 🔧 Exemple : thème Star Wars (esquisse)

| Rôle | Personnage | Traits |
|---|---|---|
| `architect` | Yoda | Sage, parle par métaphores, vision long terme |
| `lead-backend` | Obi-Wan Kenobi | Discipliné, mentor, maîtrise de la Force (du code) |
| `security-engineer` | Dark Vador | Autoritaire, ne tolère aucune faille, exhaustif |
| `product-owner` | Leia Organa | Leader née, stratège, pragmatique |
| `platform-engineer` | Han Solo | Débrouillard, pragmatique, "ça marchera" |
| `qa-automation` | C-3PO | Méticuleux, anxieux, connaît tous les protocoles |
| `dba` | R2-D2 | Efficace, fiable, communique par bips (données) |
