# Plan d'implémentation (Tasks)

**État au :** 22 novembre 2026. Une tâche = une PR vers `main` (jamais empilée), avec son
critère de fin vérifiable. On prend la **première tâche non faite** de la section « À
faire », dans l'ordre, sauf décision contraire de Muthu. La PR coche la tâche ici.

Légende : `[x]` fait · `[~]` en cours (PR ouverte) · `[ ]` à faire.

## Méthode pour chaque tâche

1. Relire la tâche, le [PRD](PRD.md), le [TRD](TRD.md) et le document concerné.
2. Créer une branche depuis `main` à jour.
3. Coder le minimum qui remplit le critère de fin ; une migration nouvelle si le schéma ou
   le catalogue change (prochain numéro : 027). Une nouvelle rubrique, un thème ou une
   unité = des lignes dans `ref.rubrique`, `ref.theme`, `ref.unite`, jamais une contrainte.
4. Tests : extrait réduit du vrai fichier dans `tests/fixtures/`, test de lecture, test de
   rejet ; `ruff` et `pytest` verts.
5. Mettre à jour les documents touchés (`docs/`, README) et la vitrine si l'utilisateur voit
   un changement.
6. Ouvrir la PR en français ; après fusion, donner à Muthu les commandes serveur complètes,
   une par bloc.

## Fait

### Appli 1 — fondations et données

- [x] **0. Fondations** (PR #1, #11, #12) — dépôt, CI, rôles, migrations, référentiel des
  territoires, installeur Debian, Caddy, sauvegarde chiffrée et test de restauration.
  *Critère :* restauration complète réussie (validé le 20/11/2026).
- [x] **1. Premier flux : estimations de population** (PR #5) — pipeline d'import, API
  séries et structure, fiche territoire (pyramide, évolution).
  *Critère :* France, Paris, Creuse, Nord, Mayotte identiques à l'INSEE (`demo verifier`).
- [x] **2a. État civil** (PR #6) — naissances, décès, fécondité, espérance de vie.
- [x] **2b. Chômage localisé** (PR #7) — BDM, trimestriel.
- [x] **2c. Recensement, activité** (PR #8) — actifs, inactifs, retraités déclarés.
- [x] **2d. Alertes et page Sources** (PR #9) — Healthchecks, `/sources`, `GET /api/v1/sources`.
- [x] **2e. Retraités DREES** (PR #10) — pensionnés (France), minimum vieillesse (département).
- [x] **Mise en ligne** — VPS netcup, `https://onepluche.duckdns.org`.

### Appli 1 — « Qui sont les Français ? »

- [x] **3. Métiers, secteurs, scolarisation** (recensement ; PR #13, fusionnée via #16).
- [x] **4. Étudiants** par formation et discipline (ministère de l'Enseignement supérieur).
- [x] **5. Santé** : personnes prises en charge par groupe de pathologies (Assurance maladie).
- [x] **6. Accueil en six blocs** (PR #16, #17) — résumé France entière, bandeau de Muthu.
- [x] **7. Nom affiché « On épluche »** (PR #18).

### Appli 2 — « De quoi les Français ont besoin ? »

- [x] **A. Fondations** (PR #19) — migration 017 : rubrique, thème, angle, bornes, seuil de
  variation, période mensuelle, poids communaux ; contrôles bornes et couverture ;
  connecteurs fichier et communes.
  *Critère :* tests verts, appli 1 inchangée.
- [x] **B1. Logement, partie 1** (PR #20) — migration 018 : logements, statut d'occupation,
  chauffage (recensement), niveau de vie et pauvreté (Filosofi).
- [x] **B2. Loyers** (PR #23) — migration 019 : poids communaux (résidences principales
  louées, recensement communal Melodi) ; Carte des loyers de l'ANIL, moyenne pondérée au
  département : `LOYER_APPARTEMENT_M2` (et par taille), `LOYER_MAISON_M2`.
- [x] **B3. Ventes et parc social** (PR #25) — migration 020 : DVF lu en flux,
  `PRIX_VENTE_M2` (appartements, maisons), calcul `ANNEES_REVENU_60M2` ; RPLS
  `LOGEMENTS_SOCIAUX`. Alsace-Moselle et Mayotte absentes de DVF.
- [x] **C1. Énergie** (PR #26) — migration 021 : Agence ORE par data-fair, électricité et
  gaz séparés (`CONSO_ELEC_RESID`, `POINTS_ELEC_RESID`, `CONSO_MOY_ELEC_LOGEMENT`, et de
  même pour le gaz) ; DPE ADEME agrégé par l'API (`DPE_ETABLIS`, `PART_DPE_FG`, avec
  l'avertissement « logements diagnostiqués seulement ») ; indice des prix BDM base 2025
  (`IPC`, mensuel, France, par poste). Groupe `demo importer energie`.
  *Critère :* une valeur par source identique au producteur.
- [x] **C2. Accès aux soins** — migration 022 : APL de la DREES aux médecins généralistes
  de 65 ans ou moins, moyenne des communes pondérée par la population standardisée
  (`APL_MG`), part des habitants sous 2,5 consultations (`PART_POP_APL_MG_FAIBLE`) ; ALD
  sans médecin traitant, Assurance maladie, département et région (`ALD_SANS_MT`) ; BPE
  Melodi, un indicateur par équipement (`LIEUX_MG`, `PHARMACIES`, `URGENCES`,
  `MAISONS_SANTE`) et densités `MG_10000`, `PHARMACIES_10000`. Groupe `demo importer soins`.
  *Critère :* une valeur par source identique au producteur.
- [x] **D1. API de l'appli 2** — filtres `rubrique` et `theme` sur `/api/v1/indicateurs` ;
  nouveau `GET /api/v1/fiche` (dernière valeur par indicateur, valeur France, source).
  *Critère :* aucune route existante ne change de forme ; tests d'API.
- [x] **D2. Fiche département `/besoins/DEP/{code}`** — migration 023 (vue
  `api.serie_age`) ; trois chiffres clés, un bloc par thème en colonnes Accès / Coût / Manque avec la valeur France, encadré 18-39 ans, lien vers
  la fiche de l'appli 1.
  *Critère :* moins d'une seconde côté serveur ; lisible à 390 px.
- [x] **D3. Vue d'ensemble `/besoins`** — migration 024 (thème `BUDGET`, comptes nationaux
  `DEPENSE_CONSO_MENAGES` par poste COICOP et `PART_DEPENSE_PRE_ENGAGEE`, groupe
  `demo importer budget`) ; budget des ménages en barres, hausse des prix depuis 2015 par
  poste, un chiffre France par thème, choix du département.
- [x] **Choix du territoire par une carte** (demande de Muthu, 21/11/2026) — sur
  `/francais` et `/besoins`, la liste des régions est remplacée par une carte de France en
  SVG (bascule Régions / Départements sur `/francais`, encart Paris et petite couronne),
  outre-mer en boutons à côté, liste complète repliée. Sans choix : France entière.
  Contours dans `web/contours.json`, régénérés par `outils/contours_svg.py`.
  *Critère :* toucher un territoire ouvre sa fiche ; aucun défilement horizontal à 390 px.
- [x] **D4. Carte des départements partagée** — reprend les contours de `web/contours.json`
  (SVG dessiné par le serveur, sans JavaScript), colorés par indicateur en une seule teinte ;
  page `/besoins/theme/{theme}` : choix de l'indicateur, valeur France, plus haut et plus
  bas, carte (outre-mer en pastilles), classement, départements sans donnée listés.
  *Critère :* clic sur un département (carte ou classement) → sa fiche.

## En cours

- [~] **8. Accueil par questions et barre latérale** (PR #21) — `/` = texte + une carte par
  question ; résumé déplacé sur `/francais` ; barre latérale (en haut sur téléphone).
  *Critère :* tests verts ; vérifié à 1280 px et 390 px, sans défilement horizontal.
- [~] **9. Vitrine au style de l'appli** (PR #22) — mêmes couleurs, test qui le vérifie,
  `CLAUDE.md` avec la règle de mise à jour.
- [~] **Mises à jour Dependabot** (PR #2, #3) — actions GitHub.

## À faire

### Commun aux applis 3 à 8

- [~] **Rubriques et thèmes en tables de référence** (migration 026) — `ref.rubrique`,
  `ref.theme`, `ref.unite` remplacent les contraintes CHECK de 017 et 024 ; l'API valide
  les filtres contre la base. Préalable aux six nouvelles applis construites en parallèle.
  *Critère :* une rubrique d'essai s'ajoute par simples INSERT (test `test_rubriques.py`).

### Appli « Comment travaillent les Français ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/GAgaMwPNpLsuJaqc3XFurA>.

- [~] **T1. Catalogue et séries INSEE** — migration 030 (rubrique `TRAVAIL`, ordre 8, sept
  thèmes, sources `INSEE_EMPLOI` et `INSEE_SIDE`), groupe `demo importer travail` : cinq jeux
  de la BDM filtrés par clé (`connecteurs/travail.py`) : chômage annuel par sexe et âge,
  emploi salarié trimestriel par secteur dont intérim (depuis 2011), emploi total salariés
  et indépendants, créations d'entreprises mensuelles dont micro-entrepreneurs, défaillances
  trimestrielles (depuis 1995). Parts de l'intérim et des indépendants calculées à l'import.
  *Critère :* Gironde 702 900 salariés au T2 2026 dont 16 289 intérimaires ; 809 244 emplois
  fin 2024 dont 105 650 indépendants (fichiers complets publiés sans rejet).
- [ ] **T2. DARES et enquête BMO** — `dares.py` (demandeurs d'emploi par département,
  somme demandée à l'API ; trimestriel régional), fichier BMO de France Travail ; contrôle
  départements contre région (écart > 3 % bloquant).
- [ ] **T3. Pages `/travail`** — vue d'ensemble, fiche département, carte par thème ; quatre
  questions guidées ; accueil, barre latérale, PRD, APP_FLOW, DESIGN et vitrine.

### Appli « Les Français sont-ils en sécurité ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/SGDKicMRrwHwF1qULSCpM2>.

- [x] **S1. Catalogue et délinquance enregistrée** (PR #35) — migration 027 (rubrique `SECURITE`, six
  familles, 32 indicateurs `FAITS_…` et `TAUX_…`), groupe `demo importer securite` : base
  départementale du SSMSI, 16 atteintes de 2016 à 2025 ; France, France métropolitaine et
  régions = somme des départements, taux rapporté à la somme des habitants ou logements.
  *Critère :* Paris 7 072 cambriolages en 2025, France 975 homicides en 2025 (fichier complet).
- [x] **S2. Routes et ressenti** (PR #37) — migration 029 : ONISR (fichiers BAAC « caractéristiques »
  et « usagers » de chaque année, deux formats, collectivités d'outre-mer écartées) : tués et
  blessés hospitalisés depuis 2016, tués par million d'habitants (vue `stat.securite_derives`) ;
  sentiment d'insécurité, France métropolitaine : enquête CVS 2007-2019 (cube data.gouv.fr)
  puis VRS 2022 et 2024 (`imports/fichiers/vrs.csv`, chiffres des fiches Insee). Taux de
  plainte reportés : publiés seulement dans les rapports PDF du SSMSI.
  *Critère :* 3 655 tués en 2016 (3 477 en métropole), 2 944 en métropole en 2021.
- [~] **S3. Pages `/securite`** — France (une carte par famille, phrase et courbe ECharts,
  évolution depuis 2016, violences sexuelles, ressenti coupé entre CVS et VRS), fiche
  département (taux, France, rang ; bandeau Paris et départements touristiques), carte par
  famille ; six questions guidées ; accueil, barre latérale, PRD, APP_FLOW, DESIGN et vitrine.
  *Critère :* chaque page s'affiche sans données, avec données, et 404 pour un département ou
  une famille inconnus (`tests/test_securite_pages.py`).

### Appli 5 « Quel avenir pour les Français ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/FTnrnv9wfVht4xEcUs5hnE>.

- [~] **A. Fondations et population** — migration 028 (rubrique `AVENIR`, sept thèmes,
  `ref.scenario`, `stat.projection`, vues `api.projection` et `api.projection_population`),
  groupe `demo importer avenir` (Omphale 2022 : trois scénarios ; France 2026), route
  `/api/v1/projections`, pages `/avenir` et `/avenir/DEP/{code}`, accueil, barre latérale,
  vitrine. *Critère :* Creuse 2018 = estimation INSEE à moins de 1 % ; France 2070 central
  65,9 millions (2026) ; tests `test_avenir_population.py`.
- [ ] **B. Climat** — DRIAS-2020 (RCP 2.6, 4.5, 8.5 ; huit indicateurs ; fichier extrait par
  Muthu et déposé dans `DEMO_DONNEES_BRUTES/drias/`), sélecteur GIEC (RCP 4.5 par défaut).
- [ ] **C. Risques naturels** — GASPAR (arrêtés de catastrophe naturelle, PPRN), pages
  `/avenir/theme/{theme}`, classements. *Critère :* Guéret, 8 arrêtés.
- [ ] **D. Questions guidées et clôture** — six questions, sept critères du dossier.

### Appli 2 — données (phases B et C)

- [~] **Courses, carburant et transports** (demande de Muthu, 21/11/2026) — migration 025,
  groupe `demo importer transports` : prix du gazole et du SP95-E10 par département (stations,
  ministère de l'Économie), part des actifs allant travailler en voiture ou en transports en
  commun, ménages sans voiture (recensement), dépense en carburants ; indice des prix de
  l'alimentation, des carburants et des transports ; courses, transports et carburant par
  ménage et par mois (France : aucune source publique de « panier moyen » par département).
  Bloc « Courses et transports » sur `/besoins`, thème Transports sur les fiches et la carte.

### Appli 2 — interface (phase D)

- [ ] **D5. Six questions guidées de l'appli 2** — formulaire en listes, réponse = phrase à
  modèle fixe + graphique + source.
- [ ] **D6. Clôture du MVP de l'appli 2** — vitrine à jour ; les sept critères du dossier
  (étape 8) vérifiés, dont deux imports du lundi passés sans intervention.

### Appli 1 — fin du MVP d'interface

- [ ] **10. Carte et classement de l'appli 1** — réutilise la carte de D4 pour les
  indicateurs de la rubrique `QUI` ; `GET /api/v1/classement`.
- [ ] **11. Comparer 2 à 4 territoires** — `/comparer` : chiffres alignés, pyramides
  superposées, courbes d'évolution.
- [ ] **12. Questions guidées de l'appli 1** — les cinq questions du dossier (pensionnés et
  actifs, évolution entre deux années, part des 60 ans et plus, vieillissement le plus
  rapide, structure par âge de deux territoires).
- [ ] **13. Export CSV** sous chaque graphique et page « Sources et méthodes » (définitions,
  limites) accessible depuis chaque chiffre.
- [ ] **14. Clôture du MVP de l'appli 1** — les sept critères du dossier (étape 8) : imports
  autonomes, source sur chaque chiffre, valeurs = INSEE, moins d'une seconde et moins de
  300 Ko en 4G, restauration testée, accès protégé, coût sous 10 €.

### Exploitation

- [ ] **E1. Sauvegardes hors site** — remplacer la destination locale provisoire
  (`/var/backups/demographie`) par un stockage chez un autre fournisseur, dans le budget.
  *Critère :* sauvegarde et restauration mensuelle réussies depuis le stockage externe.
- [ ] **E2. Vérifier Healthchecks.io sur le serveur** (`DEMO_PING_IMPORT` renseigné, alerte
  reçue lors d'un import rejeté de test).

### Après les MVP (une livraison par thème, dans cet ordre sauf avis contraire)

- [ ] Eau (qualité Hub'Eau, prix de l'eau si les fichiers sont lisibles)
- [ ] Transports (navettes, parc automobile, relevé quotidien des carburants)
- [ ] Alimentation (budget national, commerces, bio)
- [ ] Numérique (fibre, ménages sans internet)
- [ ] Garde d'enfants (taux de couverture CNAF)

Tout autre ajout (communes, Eurostat, comptes, langage naturel…) est hors périmètre : voir
le [PRD](PRD.md), section 7.
