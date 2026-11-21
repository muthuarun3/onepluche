# Documents de référence

Ces six documents décrivent **On épluche** tel qu'il existe et tel qu'il est conçu. Ils
résument les deux dossiers de conception validés par Muthu et le code de `main`. Toute
personne, ou tout assistant de code, qui travaille sur le dépôt les lit avant de commencer.

| Document | Rôle | Question à laquelle il répond |
| --- | --- | --- |
| [PRD.md](PRD.md) | Produit | Quoi et pourquoi : problème, utilisateurs, fonctionnalités, hors périmètre |
| [TRD.md](TRD.md) | Technique | Avec quoi : pile, architecture, règles entre modules, sécurité, déploiement |
| [APP_FLOW.md](APP_FLOW.md) | Parcours | Où va-t-on : pages, liens, interactions, adresses |
| [DESIGN.md](DESIGN.md) | Charte UI-UX | À quoi ça ressemble : couleurs, typographie, composants, mobile, mode sombre |
| [SCHEMA.md](SCHEMA.md) | Base de données | Comment c'est stocké : schémas, tables, vues, rôles, contraintes |
| [TASKS.md](TASKS.md) | Plan d'implémentation | Dans quel ordre : tâches faites, en cours, à venir, avec leur critère de fin |

## Règles d'usage

1. **Le périmètre est fermé.** Une fonctionnalité, une dépendance ou une source absente de
   ces documents n'est pas ajoutée sans l'accord de Muthu. En cas de doute, on demande.
2. **Une tâche à la fois.** On prend la prochaine tâche de [TASKS.md](TASKS.md), on la livre
   dans une PR vers `main` (pas de PR empilée), et on coche la tâche dans la même PR.
3. **Les documents suivent le code.** Une PR qui change une page, une table, une dépendance
   ou une décision met à jour le document concerné dans la même PR.
4. **Les dossiers de conception font foi** en cas de désaccord avec ces résumés :
   - appli 1 « Qui sont les Français ? » : <https://claude.ai/artifact/T972JhFcFecQN9YNRSA94q>
   - appli 2 « De quoi les Français ont besoin ? » : <https://claude.ai/artifact/UUFRVFVGhw9v9mZcF6wX9u>
5. **Tout en français** : code métier, commentaires, commits, PR, documents.

État décrit : 21 novembre 2026 (`main` après la PR #20 ; PR #21 et #22 ouvertes).
