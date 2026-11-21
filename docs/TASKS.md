# Plan d'implémentation (Tasks)

**État au :** 21 novembre 2026. Une tâche = une PR vers `main` (jamais empilée), avec son
critère de fin vérifiable. On prend la **première tâche non faite** de la section « À
faire », dans l'ordre, sauf décision contraire de Muthu. La PR coche la tâche ici.

Légende : `[x]` fait · `[~]` en cours (PR ouverte) · `[ ]` à faire.

## Méthode pour chaque tâche

1. Relire la tâche, le [PRD](PRD.md), le [TRD](TRD.md) et le document concerné.
2. Créer une branche depuis `main` à jour.
3. Coder le minimum qui remplit le critère de fin ; une migration nouvelle si le schéma ou
   le catalogue change (prochain numéro : 019).
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

## En cours

- [~] **8. Accueil par questions et barre latérale** (PR #21) — `/` = texte + une carte par
  question ; résumé déplacé sur `/francais` ; barre latérale (en haut sur téléphone).
  *Critère :* tests verts ; vérifié à 1280 px et 390 px, sans défilement horizontal.
- [~] **9. Vitrine au style de l'appli** (PR #22) — mêmes couleurs, test qui le vérifie,
  `CLAUDE.md` avec la règle de mise à jour.
- [~] **Mises à jour Dependabot** (PR #2, #3) — actions GitHub.

## À faire

### Appli 2 — données (phases B et C)

- [~] **B2. Loyers** (PR #23) — poids communaux (résidences principales louées, recensement
  communal Melodi) ; connecteur Carte des loyers (CSV Latin-1, virgule décimale, un jeu
  data.gouv par année trouvé par recherche) ; indicateur `LOYER_ANNONCE_M2` par type de
  bien, moyenne pondérée au département.
  *Critère :* Creuse et Paris identiques à la source (`demo verifier`) ; bornes 3-60 €/m².
- [ ] **B3. Ventes et parc social** — DVF lu par département en flux : ventes d'un seul
  logement, surface ≥ 9 m², prix ≥ 1 000 €, 1 % extrêmes exclus, médiane publiée seulement
  au-dessus de 30 ventes, Alsace-Moselle et Mayotte déclarées absentes ; `PRIX_VENTE_M2`,
  `VENTES` ; RPLS `LOGEMENTS_SOCIAUX` ; calcul `ANNEES_REVENU_60M2` (« calcul On épluche »).
  *Critère :* une valeur par source identique au producteur ; seuil de variation 15 % pour
  les prix.
- [ ] **C1. Énergie** — Agence ORE par data-fair (`CONSO_RESIDENTIELLE`,
  `POINTS_LIVRAISON_RESID`, `CONSO_MOY_LOGEMENT`) ; DPE ADEME agrégé par l'API
  (`DPE_ETABLIS`, `PART_DPE_FG`, avec l'avertissement « logements diagnostiqués seulement ») ;
  indice des prix Melodi (`IPC`, mensuel, France). Groupe `demo importer energie`.
  *Critère :* une valeur par source identique au producteur.
- [ ] **C2. Accès aux soins** — BPE santé (`EQUIPEMENTS_SANTE`, `PHARMACIES_10000`,
  `MG_10000`) ; APL DREES agrégé par population communale (`APL_MG`) ; ALD sans médecin
  traitant (`ALD_SANS_MT`, maille à confirmer). Groupe `demo importer soins`.
  *Critère :* une valeur par source identique au producteur.

### Appli 2 — interface (phase D)

- [ ] **D1. API de l'appli 2** — filtres `rubrique` et `theme` sur `/api/v1/indicateurs` ;
  nouveau `GET /api/v1/fiche` (dernière valeur par indicateur, valeur France, source).
  *Critère :* aucune route existante ne change de forme ; tests d'API.
- [ ] **D2. Fiche département `/besoins/DEP/{code}`** — trois chiffres clés, un bloc par
  thème en colonnes Accès / Coût / Manque avec la valeur France, encadré 18-39 ans, lien vers
  la fiche de l'appli 1.
  *Critère :* moins d'une seconde côté serveur ; lisible à 390 px.
- [ ] **D3. Vue d'ensemble `/besoins`** — budget des ménages par poste (France), évolution
  des prix depuis 2015, un chiffre France par thème, choix du département.
- [ ] **D4. Carte des départements partagée** — contours IGN Admin Express simplifiés
  (environ 300 Ko, versionnés), dessinés par ECharts ; page `/besoins/theme/{theme}` : carte,
  classement, valeur France.
  *Critère :* clic sur un département → sa fiche ; départements sans donnée signalés.
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
