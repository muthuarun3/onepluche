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
├── /avenir                        Quel avenir pour les Français ? vue France        🔶
│   ├── /avenir/DEP/{code}         Fiche département : population projetée, âges    🔶
│   └── /avenir/theme/{theme}      Carte et classement d'un thème                    ⬜
├── /securite                      Les Français sont-ils en sécurité ? vue France   ✅
│   ├── /securite/DEP/{code}       Fiche département : taux, France, rang           ✅
│   └── /securite/famille/{famille} Carte et classement d'une famille d'atteintes   ✅
├── /travail                       Comment travaillent les Français ? vue France     🔶
│   ├── /travail/DEP/{code}        Fiche département : mêmes blocs, France, rang     🔶
│   └── /travail/theme/{theme}     Carte et classement (taux et parts)               🔶
├── /argent-public                 Où va l'argent public ? vue France               🔶
│   ├── /argent-public/etat        Budget de l'État                                 ⬜
│   ├── /argent-public/DEP/{code}  Fiche département : dépenses locales, CatNat     ⬜
│   └── /argent-public/menage      Impôts d'un ménage type                          ⬜
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
| Carte « Quel avenir pour les Français ? » | `/avenir` |
| Carte « Les Français sont-ils en sécurité ? » | `/securite` |
| Carte « Comment travaillent les Français ? » | `/travail` |
| Carte « Où va l'argent public ? » | `/argent-public` |

### Qui sont les Français ? `/francais` (✅ sur `/` aujourd'hui, 🔶 déplacé par la PR #21)

| Élément | Au clic |
| --- | --- |
| Six blocs (combien, âge, activité, métiers, études, santé) : phrase, chiffres, barres | Lien « Évolution depuis 1975 » ou « Pyramide des âges » → `/territoire/FRANCE/FR` |
| Barres | Survol : infobulle avec l'effectif (attribut `title`) |
| Santé : « Les N autres groupes » | Déplie la liste (`<details>`, sans JavaScript) |
| Carte « Choisir un territoire » en tête de page, bascule Régions / Départements (sans JavaScript) | Toucher une région ou un département de métropole → `/territoire/{niveau}/{code}` ; Paris et la petite couronne dans un encart agrandi |
| Boutons « Outre-mer » à côté de la carte (Guadeloupe, Martinique, Guyane, La Réunion, Mayotte) | Fiche de la région ou du département, selon la bascule |
| « Liste de tous les territoires » (repliée) : France, France métropolitaine, 18 régions avec leurs départements | `/territoire/{niveau}/{code}` |

Sans choix, la page montre la France entière : la carte ne filtre rien, elle ouvre une fiche.

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
| `/besoins` | Courses et transports : dépense moyenne par ménage et par mois (courses alimentaires, transports, carburant ; France) et prix du litre de gazole et de SP95-E10 (moyenne des stations de métropole, lien vers la carte) ; part de chaque poste dans la dépense de consommation des ménages et part des dépenses pré-engagées dans leur revenu (comptes nationaux, France) ; hausse des prix depuis 2015 en barres (ensemble, énergie, électricité, gaz, loyers, santé, alimentation, carburants, transports ; moyennes annuelles, dernière année complète) ; un chiffre France par thème ; carte des départements en tête de page (outre-mer en boutons, liste complète repliée) | Toucher un département → `/besoins/DEP/{code}` ; thème → `/besoins/theme/{theme}` |
| `/besoins/DEP/{code}` | Trois chiffres clés (loyer au m², part des DPE F ou G, accès aux généralistes) ; un bloc par thème en trois colonnes Accès, Coût, Manque, valeur France à côté ; encadré 18-39 ans | Lien vers `/territoire/DEP/{code}` (même département dans l'appli 1) ; lien vers chaque thème |
| `/besoins/theme/{theme}` (`logement`, `energie`, `soins`…) | Onglets des thèmes ; définition de l'indicateur ; valeur France (masquée pour les effectifs), département le plus haut et le plus bas ; carte en une seule teinte (outre-mer en médaillons) ; classement ; départements sans donnée listés | Liste de l'indicateur (`?indicateur=`, recharge la page) ; clic sur un département (carte ou classement) → sa fiche ; indicateur ou thème inconnu → 404 |

### Rubrique `/securite` (✅, appli 4)

| Page | Contenu | Interactions |
| --- | --- | --- |
| `/securite` | Une carte par famille (personnes, vols, biens, stupéfiants, routes) : l'atteinte phare en grand avec sa phrase (« 211 596 cambriolages de logement enregistrés en 2025, 15 % de moins qu'en 2016 »), sa courbe depuis 2016 et les autres atteintes dépliables ; « La délinquance augmente-t-elle ? » (atteintes en hausse, stables ou en baisse depuis 2016) ; violences sexuelles ; le ressenti (trois parts, courbe coupée entre les enquêtes CVS et VRS), toujours après les faits ; six questions guidées ; carte des départements | Toucher un département → `/securite/DEP/{code}` ; « Comparer les départements » → `/securite/famille/{famille}` ; questions guidées → ancre de la page ou carte |
| `/securite/DEP/{code}` | Bandeau pour Paris et les départements très touristiques ; par famille, chaque atteinte : taux du département, taux France, rang parmi les départements (1 = le plus élevé), nombre | Lien vers `/territoire/DEP/{code}` ; vers chaque famille ; département inconnu → 404 |
| `/securite/famille/{famille}` (`personnes`, `vols`, `biens`, `stupefiants`, `routes`) | Onglets des familles ; taux seulement (pour 1 000 habitants ou logements, tués par million) ; valeur France, plus haut et plus bas ; carte colorée ; classement | `?indicateur=` ; famille inconnue, `ressenti` (France seulement) ou indicateur d'une autre famille → 404 |

### Rubrique `/travail` (🔶, appli travail)

| Page | Contenu | Interactions |
| --- | --- | --- |
| `/travail` | Quatre questions guidées (liens vers les blocs) ; « Qui cherche et qui crée » : chômage (phrase « France : 8,3 % de chômeurs au 2e trimestre 2026, contre 7,5 % un an plus tôt », 15-24 ans, courbe depuis 1982), demandeurs d'emploi (A, B, C et A, part depuis un an ou plus, courbe), métiers qui peinent à recruter (5 plus difficiles parmi ceux d'au moins 50 projets, 10 qui recrutent le plus, familles), créations sur 12 mois et défaillances sur 4 trimestres (courbe par année) ; « Qui travaille » : salariés par secteur et évolution sur un an, intérim, indépendants ; carte des départements | Toucher un département → `/travail/DEP/{code}` ; « Comparer les départements » → `/travail/theme/{theme}` ; famille de métiers → carte de cette famille |
| `/travail/DEP/{code}` | Les mêmes blocs pour le département, avec la valeur France et le rang (1 = la plus élevée) des taux et parts ; courbe du chômage sur 10 ans à côté de la France | Lien vers `/territoire/DEP/{code}` (métiers exercés) ; département inconnu → 404 |
| `/travail/theme/{theme}` (`chercher-creer`, `emploi`) | Onglets des thèmes ; taux et parts seulement (chômage, longue durée, recrutements difficiles ; intérim, indépendants) ; pour les recrutements difficiles, onglets des 8 familles de métiers ; valeur France, plus haut, plus bas, carte colorée, classement | `?indicateur=`, `?famille=` ; thème, indicateur ou famille inconnus → 404 |

Absences de données affichées comme telles (exemple : Alsace-Moselle et Mayotte pour DVF),
jamais comme zéro : « — » et « Pas de donnée pour ce département ». Sur la fiche, la valeur
France n'est pas montrée à côté des effectifs (nombre de pharmacies, d'urgences…), qui ne
se comparent pas à un total national ; l'indice des prix, national, n'y figure pas.

### Rubrique `/avenir` (🔶, appli 5 phase A)

| Page | Contenu | Interactions |
| --- | --- | --- |
| `/avenir` | Population de la France d'ici 2070 (projections nationales 2026) : phrase (scénario central, maximum, fourchette), courbe du scénario central dans la bande population basse - population haute, tableau par grand groupe d'âge ; carte des départements ; avertissement sur les projections départementales de 2022 ; blocs « Climat » et « Risques naturels » annoncés | Toucher un département → `/avenir/DEP/{code}` |
| `/avenir/DEP/{code}` | Quatre chiffres en 2050 (population et fourchette, évolution depuis 2018, part des 75 ans ou plus, seniors pour 100 actifs ; France = somme des départements à côté) ; phrase ; courbe et bande des trois scénarios avec tableau 2018, 2030, 2050, 2070 ; pyramide des âges projetée (scénario central) avec le contour de 2018 | Liste de l'année de la pyramide (sans rechargement) ; liens vers `/territoire/DEP/{code}` et `/besoins/DEP/{code}` ; département sans projection importée : message ; inconnu → 404 |

### Rubrique `/argent-public` (🔶, PR A)

| Page | Contenu | Interactions |
| --- | --- | --- |
| `/argent-public` | Quatre chiffres (dépense publique de la dernière année en Md€ et en % du PIB, par habitant, déficit, dette du dernier trimestre) ; trois questions guidées ; « Pour 1 000 € de dépense publique » (barres par fonction) ; « Qui dépense ? » ; « D'où vient l'argent ? » (avec la part empruntée) ; intérêts de la dette comparés à la défense et à l'enseignement ; déficit et dette en % du PIB depuis 1978 ; dette en milliards ; blocs à venir (État, département, ménage type, catastrophes naturelles) | Bascule « Euros de N / Euros de l'époque » sur la courbe de la dette (sans rechargement) ; questions → ancres de la page ; sans données : bandeau |

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
