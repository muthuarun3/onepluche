# App Flow — Parcours et navigation

**État au :** 21 novembre 2026. Légende : ✅ en service · 🔶 PR ouverte · ⬜ prévu.

## 1. Entrée dans l'application

```text
Navigateur ──► https://onepluche.duckdns.org
                 │
                 ▼
     Caddy demande identifiant et mot de passe (fenêtre du navigateur)
                 │  refus : nouvelle demande, aucune page servie
                 ▼ accepté
              Accueil  /
```

- Il n'y a **ni page de connexion, ni inscription, ni déconnexion, ni paramètres** dans
  l'application : l'authentification est faite par Caddy avant toute page. Le navigateur
  garde l'identifiant pour la session.
- Toutes les pages et l'API sont derrière cette protection. `/sante` aussi (supervision
  depuis le serveur lui-même).
- La vitrine <https://onepluche.neocities.org> est publique et statique ; elle renvoie vers
  l'appli.

## 2. Carte des pages

```text
/                                  Accueil : texte + une carte par question         🔶
├── /francais                      Qui sont les Français ? (résumé 6 blocs)        🔶 (aujourd'hui sur /)
│   ├── /territoire/FRANCE/{FR|FM} Fiche France, France métropolitaine             ✅
│   ├── /territoire/REG/{code}     Fiche région                                     ✅
│   ├── /territoire/DEP/{code}     Fiche département                                ✅
│   ├── /comparer                  2 à 4 territoires côte à côte                    ⬜
│   ├── /carte                     Carte et classement d'un indicateur              ⬜
│   └── /questions                 Questions guidées de l'appli 1                   ⬜
├── /besoins                       De quoi les Français ont besoin ? vue d'ensemble ✅
│   ├── /besoins/DEP/{code}        Fiche département : thèmes × Accès/Coût/Manque  ✅
│   └── /besoins/theme/{theme}     Carte et classement d'un thème                   ✅
├── /sources                       État des imports, licences                       ✅
└── /api/docs                      Documentation de l'API (Swagger)                 ✅
```

Adresses invalides : un niveau autre que `FRANCE`, `REG`, `DEP` ou un code hors motif
`^[0-9A-Z]{2,3}$` renvoie une erreur 422 ; un territoire inconnu renvoie 404.

## 3. Navigation commune (🔶 PR #21)

Chaque page hérite de `base.html` :

| Zone | Contenu | Comportement |
| --- | --- | --- |
| Barre latérale (ordinateur, 15rem à gauche, fixe au défilement) | « On épluche » (lien vers `/`), Accueil, une entrée par question, puis Sources et API | L'entrée de la page courante est mise en évidence (`aria-current="page"`), y compris pour les sous-pages (`/besoins/...`) |
| Barre du haut (téléphone, moins de 48rem) | Les mêmes liens, en ligne, qui passent à la ligne | Aucun menu repliable, aucun JavaScript |
| Pied de page | Producteurs des données, Licence Ouverte 2.0, ECharts | — |

La liste des questions vient d'une seule constante (`QUESTIONS` dans `web/pages.py`), lue
par l'accueil et par la barre latérale. Ajouter une application = ajouter une entrée.

## 4. Pages et interactions

### Accueil `/` (🔶)

| Élément | Au clic |
| --- | --- |
| Bandeau de Muthu (30 ans, présidentielle) | — |
| Carte « Qui sont les Français ? » | `/francais` |
| Carte « De quoi les Français ont besoin ? » | `/besoins` |

### Qui sont les Français ? `/francais` (✅ sur `/` aujourd'hui, 🔶 déplacé par la PR #21)

| Élément | Au clic |
| --- | --- |
| Six blocs (combien, âge, activité, métiers, études, santé) : phrase, chiffres, barres | Lien « Évolution depuis 1975 » ou « Pyramide des âges » → `/territoire/FRANCE/FR` |
| Barres | Survol : infobulle avec l'effectif (attribut `title`) |
| Santé : « Les N autres groupes » | Déplie la liste (`<details>`, sans JavaScript) |
| Choisir un territoire : France, France métropolitaine, 18 régions avec leurs départements | `/territoire/{niveau}/{code}` |

Un bloc dont les données ne sont pas encore importées n'apparaît pas.

### Fiche territoire `/territoire/{niveau}/{code}` (✅)

| Élément | Interaction |
| --- | --- |
| Fil d'Ariane : Accueil (→ `/francais` après #21) › région parente | Lien |
| Chiffres clés : population, moins de 20 ans, 60 et plus, 75 et plus, indice de vieillissement | Survol : définition de l'indicateur |
| Pyramide des âges | Liste « Année » : redessine la pyramide pour l'année choisie, sans recharger la page |
| « Voir le tableau » | Déplie le tableau hommes / femmes par tranche |
| Évolution de la population | Courbe ECharts ; pointillés pour les années provisoires ; survol : valeur |
| Territoires rattachés | Liens vers les fiches enfants (régions d'un pays, départements d'une région) |
| Source | Lien vers le producteur, licence, date de mise à jour, avertissement |

Sans données : message « Aucune donnée importée pour ce territoire ».

### Sources `/sources` (✅)

Tableau : source, fichier, état (À jour, En attente de validation, Dernier fichier rejeté,
Import en cours, Pas encore importé), dernière publication, millésime, lien et licence.
Défilement horizontal du seul tableau sur téléphone.

### Rubrique `/besoins` (🔶, appli 2 phase D)

| Page | Contenu | Interactions |
| --- | --- | --- |
| `/besoins` | Part de chaque poste dans la dépense de consommation des ménages et part des dépenses pré-engagées dans leur revenu (comptes nationaux, France) ; hausse des prix depuis 2015 en barres (ensemble, énergie, électricité, gaz, loyers, santé ; moyennes annuelles, dernière année complète) ; un chiffre France par thème ; choix du département | Choix du département → `/besoins/DEP/{code}` ; thème → `/besoins/theme/{theme}` |
| `/besoins/DEP/{code}` | Trois chiffres clés (loyer au m², part des DPE F ou G, accès aux généralistes) ; un bloc par thème en trois colonnes Accès, Coût, Manque, valeur France à côté ; encadré 18-39 ans | Lien vers `/territoire/DEP/{code}` (même département dans l'appli 1) ; lien vers chaque thème |
| `/besoins/theme/{theme}` (`logement`, `energie`, `soins`…) | Onglets des thèmes ; définition de l'indicateur ; valeur France (masquée pour les effectifs), département le plus haut et le plus bas ; carte en une seule teinte (outre-mer en médaillons) ; classement ; départements sans donnée listés | Liste de l'indicateur (`?indicateur=`, recharge la page) ; clic sur un département (carte ou classement) → sa fiche ; indicateur ou thème inconnu → 404 |

Absences de données affichées comme telles (exemple : Alsace-Moselle et Mayotte pour DVF),
jamais comme zéro : « — » et « Pas de donnée pour ce département ». Sur la fiche, la valeur
France n'est pas montrée à côté des effectifs (nombre de pharmacies, d'urgences…), qui ne
se comparent pas à un total national ; l'indice des prix, national, n'y figure pas.

### Questions guidées (⬜)

Formulaire de paramètres en listes (territoire, année, indicateur) → envoi en `GET` (adresse
partageable) → réponse : une phrase à modèle fixe dont les chiffres sont lus en base, un
graphique, la source. Une question hors données reçoit « ces données n'existent pas »
avec la raison.

Questions de l'appli 2 : années de niveau de vie pour 60 m² ; loyer comparé au reste de la
France ; part des passoires énergétiques ; manque de généralistes ; pauvreté des 18-39 ans ;
prix qui ont le plus augmenté depuis 2015 (France).

## 5. Redirections et états

| Situation | Résultat |
| --- | --- |
| Pas d'identifiant ou mauvais mot de passe | 401 de Caddy, aucune page servie |
| Adresse inconnue | 404 de FastAPI |
| Paramètre hors motif | 422 avec le détail de l'erreur |
| Requête de lecture de plus de 5 s | Erreur 500 (délai de la base) ; ne doit pas arriver, une fiche se charge en moins d'une seconde |
| Données absentes | Bloc masqué (résumé) ou message explicite (fiche) |

Aucune redirection applicative n'existe aujourd'hui : pas de session, pas de tableau de bord
personnel. Si `/` change de rôle (PR #21), l'ancien contenu passe à `/francais` sans
redirection automatique.
