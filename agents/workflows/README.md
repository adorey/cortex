# Workflows

> *"Un plan, c'est une liste de choses qui ne se passeront pas exactement comme prévu — mais qui cadre quand même mieux que l'improvisation totale."* — Ford Prefect

## 🎯 Qu'est-ce qu'un workflow ?

Un workflow est une **trame d'orchestration** : une séquence d'étapes, d'agents et de checklists à suivre pour un contexte récurrent.

Ce n'est pas un script rigide. C'est un filet de sécurité pour ne rien oublier.

| Couche | Répond à |
|---|---|
| `roles/` | **QUOI** faire |
| `stacks/` | **COMMENT** le faire |
| `personalities/` | **QUI** tu es |
| `project-context.md` | **OÙ** tu travailles |
| `workflows/` | **DANS QUEL ORDRE et AVEC QUI** |

## 📁 Deux niveaux

```
cortex/agents/workflows/        ← Workflows génériques (ce dossier)
    ├── feature-development.md
    ├── tech-watch.md
    └── ...

{projet}/agents/workflows/      ← Workflows spécifiques au projet hôte
    ├── rfp-response.md
    └── ...
```

**Règle de priorité :** le workflow projet prime sur le workflow générique portant le même nom.

## 🔄 Rôle du Prompt Manager

Le Prompt Manager est le **seul point d'entrée**. À chaque demande il :

1. Analyse le prompt
2. Recherche un workflow correspondant — d'abord dans `{projet}/agents/workflows/`, puis ici
3a. **Workflow trouvé** → l'annonce, l'active et orchestre les étapes
3b. **Pas de workflow** → dispatch classique vers l'expert
3c. **Cas récurrent sans workflow** → propose d'en créer un

## 📝 Workflows disponibles

| Fichier | Contexte de déclenchement |
|---|---|
| `feature-development.md` | Développement d'une nouvelle fonctionnalité |
| `tech-watch.md` | Veille technologique sur un sujet ou outil |

## ➕ Créer un workflow projet

Utilisez le template `cortex/templates/workflow.md.template` et placez votre fichier dans `{projet}/agents/workflows/`.
