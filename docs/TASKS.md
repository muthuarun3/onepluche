# Plan d'implémentation (Tasks)

**État au :** 22 novembre 2026. Une tâche = une PR vers `main` (jamais empilée), avec son
critère de fin vérifiable. On prend la **première tâche non faite** de la section « À
faire », dans l'ordre, sauf décision contraire de Muthu. La PR coche la tâche ici.

Légende : `[x]` fait · `[~]` en cours (PR ouverte) · `[ ]` à faire.

## Méthode pour chaque tâche

1. Relire la tâche, le [PRD](PRD.md), le [TRD](TRD.md) et le document concerné.
2. Créer une branche depuis `main` à jour.
3. Coder le minimum qui remplit le critère de fin ; une migration nouvelle si le schéma ou
   le catalogue change (prochain numéro : 048). Une nouvelle rubrique, un thème ou une unité = des lignes dans `ref.rubrique`, `ref.theme`, `ref.unite`, jamais une contrainte.
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
- [x] **Macro-catégorie « Données »** (PR #46) — titre « Données » dans la barre latérale
  au-dessus des questions, accueil « Données » puis « Programmes » annoncé, vitrine.
  *Critère :* `tests/test_import.py::test_pages` ; vérifié à 1280 px et 390 px.
- [x] **Macro-catégorie « Programmes » : conception** — dossier en dix étapes validé le
  24/11/2026 : <https://claude.ai/artifact/VWJAXgpAa9xJvhY6YLJZmC>. Tâches P1 à P5 ci-dessous.

## À faire

### Programmes (présidentielle 2027)

Une PR à la fois, sur `main` à jour. Fiches en TOML dans `programmes/2027/`, publiées par la
fusion d'une PR relue par Muthu ; aucun modèle de langage, aucun mot de jugement.

- [x] **P1. Fondations** (PR #54, fusionnée avec #53) — `programmes/2027/sujets.toml` (12 sujets, échelles
  communes), `donnees/programmes.py` (modèles Pydantic, contrôles croisés, ordre des
  candidats, comparaison par sujet), fiches fictives dans `tests/fixtures/programmes/`.
  *Critère :* une fiche cassée est refusée avec le nom du fichier
  (`tests/test_programmes_fiches.py`).
- [x] **P2. Veille** (PR #58, fusionnée avec #57) — migration 045 `ingest.programme_releve` et vue
  `api.programme_releve`, `imports/veille_programmes.py`, `programmes/2027/suivis.toml`
  (vide tant qu'aucun programme n'est suivi), `demo veiller programmes` (minuteur
  `demographie-veille-programmes.timer`, lundi 7 h 15), copies dans
  `$DEMO_DONNEES_BRUTES/programmes` (donc sauvegardées avec les fichiers bruts), battement
  facultatif `DEMO_PING_PROGRAMMES`, tableau sur `/sources`. *Critère :* un changement
  d'empreinte alerte (`tests/test_programmes_veille.py`) ; première veille réelle sur le
  serveur.
- [~] **P3. Écrans** (PR en cours) — `/programmes`, `/programmes/{candidat}`,
  `/programmes/comparer?sujet=`, `/api/v1/programmes` et `/api/v1/programmes/{candidat}`,
  migration 047 (vue `api.rubrique`, pour relier chaque chiffre de contexte à son appli),
  titre « Programmes » dans la barre latérale, deux cartes sur l'accueil, vitrine.
  *Critère :* critères 1, 3 et 5 de l'étape 8 du dossier (`tests/test_programmes_pages.py`,
  captures 1280 et 390 px).
- [ ] **P4. Premier vrai programme** — fiche du premier candidat déclaré qui a publié un texte,
  relue par Muthu. *Critère :* critère 6 ; veille sans erreur deux lundis de suite.
- [ ] **P5 et suivantes** — une PR par programme ou nouvelle version ; mars 2027 : liste du
  Conseil constitutionnel (statuts, ordre officiel) ; avril 2027 : professions de foi.

### Commun aux applis 3 à 8

- [x] **Rubriques et thèmes en tables de référence** (migration 026, PR #34) — `ref.rubrique`,
  `ref.theme`, `ref.unite` remplacent les contraintes CHECK de 017 et 024 ; l'API valide
  les filtres contre la base. Préalable aux six nouvelles applis construites en parallèle.
  *Critère :* une rubrique d'essai s'ajoute par simples INSERT (test `test_rubriques.py`).

### Appli « Que pensent et votent les Français ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/7cb5CjJyHwvtypASUQLfCu>.

- [x] **V1. Fondations** (PR #40) — migration 032 : rubrique `VOTES` (`/votes`, ordre 4), thèmes
  `PARTICIPATION`, `RESULTATS`, `ELUS`, sources `MI_ELECTIONS` et `MI_RNE`, territoires
  `HORS_DEP` (`ZZ`, `COM`), type de période `SCRUTIN`, 20 tours dans `ref.scrutin`,
  `ref.choix_scrutin` et `ref.ajouter_choix`, dimension `mandat`, vues `api.scrutin` et
  `api.choix_scrutin` ; dépendance `pyarrow`. *Critère :* `tests/test_votes_fondations.py`.
- [x] **V2. Résultats** (PR #45) — migration 036 ; groupe `demo importer votes`,
  connecteur `elections.py` (Parquet data.gouv.fr par bureau de vote, lu par paquets avec
  pyarrow et additionné par département ; même date de mise à jour = rien n'est téléchargé),
  indicateurs `INSCRITS`, `VOTANTS`, `ABSTENTIONS`, `BLANCS`, `NULS`, `BLANCS_ET_NULS`,
  `EXPRIMES`, `VOIX` ; contrôles d'égalité stricts dans le connecteur et somme France =
  départements + hors département ; vues `api.participation` et `api.resultat` (à la place
  de `stat.votes_derives`). *Critère :* totaux France égaux aux chiffres officiels
  (vérifié sur le fichier complet pour 2022 et 2024), `tests/test_votes_resultats.py`.
- [~] **V3. Élus** (PR #53) — migration 041 ; connecteur `elus.py` dans le groupe
  `votes` (Répertoire national des élus, quatre fichiers trouvés par leur titre dans l'API
  data.gouv.fr : maires, conseillers départementaux, députés, sénateurs). Un indicateur par
  mandat (`ELUS_MAIRES`, `ELUS_CONSEILLERS_DEP`, `ELUS_DEPUTES`, `ELUS_SENATEURS`) ventilé
  par sexe, tranche d'âge et groupe socioprofessionnel (dimension `pcs` de la population),
  `AGE_MEDIAN_ELUS` par mandat ; vue `api.elus` (part de femmes, part des moins de 40 ans).
  Aucun nom en base. *Critère :* `tests/test_votes_elus.py`.
- [ ] **V4. Carte et fiche** — `/votes`, `/votes/DEP/{code}`, routes `/api/v1/scrutins`.
- [ ] **V5. Scrutin et finitions** — `/votes/scrutin/{id}`, croisement avec les rubriques 1
  et 2 (corrélation, pas cause), six questions guidées, accueil, barre latérale, critères de
  fin du dossier.

### Appli 3 « Comment vivent les Français ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/NoW5WiUnhSjjceKtjqXTfu>.

- [x] **A1. Catalogue, revenus détaillés et salaires** — migration 031 (rubrique `VIVRE`,
  sept thèmes, `ref.indicateur_affichage` et les six indicateurs partagés des applis 1 et 2,
  14 indicateurs Filosofi, `SALAIRE_NET_MOYEN`), groupe `demo importer vivre` : Filosofi
  détaillé, salaires BTS par sexe × catégorie et sexe × âge. *Critère :* Creuse D9 = 37 240 €,
  Paris 3 836 €, France 2 733 € (2024) ; 97 et 101 départements sur les fichiers complets.
- [~] **A2. Séries nationales** — migration 043 (13 indicateurs, sources `INSEE_ERFS` et
  `INSEE_ENQPAT`, modalités `decile_niveau_vie`, `placement` et catégories de l'enquête
  Patrimoine), dix jeux de plus dans `demo importer vivre` : salaire moyen du privé depuis
  1996, ERFS (1996-2024, métropole), comptes des ménages (pouvoir d'achat par unité de
  consommation, revenu disponible, taux d'épargne et d'épargne financière), patrimoine
  (enquête 2024 par âge, catégorie et décile de niveau de vie ; placements financiers) ;
  pension moyenne lue avec les retraités (`demo importer retraites`). *Critère :* taux
  d'épargne 2025 = 17,9 % (provisoire) ; fichiers complets lus sans rejet.
- [ ] **B. CAF et Banque de France** — `caf.py` (RSA, aides au logement, décembre),
  `surendettement.py` (13 XLSX régionaux), vue `stat.vivre_derives` (quatre calculs propres).
- [ ] **C. Pages `/vivre`** — vue France, fiche département, page thème, six questions
  guidées ; accueil, barre latérale, APP_FLOW, DESIGN, vitrine ; sept critères du dossier.

### Appli « Comment travaillent les Français ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/GAgaMwPNpLsuJaqc3XFurA>.

- [x] **T1. Catalogue et séries INSEE** — migration 030 (rubrique `TRAVAIL`, ordre 8, sept
  thèmes, sources `INSEE_EMPLOI` et `INSEE_SIDE`), groupe `demo importer travail` : cinq jeux
  de la BDM filtrés par clé (`connecteurs/travail.py`) : chômage annuel par sexe et âge,
  emploi salarié trimestriel par secteur dont intérim (depuis 2011), emploi total salariés
  et indépendants, créations d'entreprises mensuelles dont micro-entrepreneurs, défaillances
  trimestrielles (depuis 1995). Parts de l'intérim et des indépendants calculées à l'import.
  *Critère :* Gironde 702 900 salariés au T2 2026 dont 16 289 intérimaires ; 809 244 emplois
  fin 2024 dont 105 650 indépendants (fichiers complets publiés sans rejet).
- [x] **T2. DARES et enquête BMO** — migration 034 (sources `DARES` et `FT_BMO`, 217 métiers
  et 8 familles BMO), `connecteurs/dares.py` : demandeurs d'emploi A et ABC par département,
  région et France, chaque trimestre depuis 1996, corrigés des variations saisonnières, par
  sexe et âge, dont inscrits depuis un an ou plus (export CSV de l'API ouverte de la DARES ;
  les départements font la somme de la France à 0,03 % près, ce qui remplace le contrôle
  départements contre région prévu) ; `connecteurs/bmo.py` : fichiers xlsx de l'enquête BMO
  (2025 et après, trouvés sur data.gouv.fr), bassins additionnés par département, par famille
  et par métier, part des projets difficiles calculée à l'import.
  *Critère :* Gironde 156 520 demandeurs d'emploi ABC au T3 2026 dont 45,8 % depuis un an
  ou plus ; 67 045 projets de recrutement en 2026 dont 47,1 % jugés difficiles.
- [x] **T3. Pages `/travail`** — `web/travail.py` : vue France, fiche département, carte par
  thème (`chercher-creer`, `emploi`, familles de métiers BMO) ; quatre questions guidées avec
  leur bloc ; migration 035 (vue `api.ventilation` : sexe, âge et modalités, que `api.serie`
  ne montre pas) ; accueil, barre latérale, pied de page, vitrine, PRD, APP_FLOW, DESIGN.
  *Critère :* fiche Gironde avec 156 520 demandeurs d'emploi, 67 045 projets dont 47,1 %
  difficiles, 702 900 salariés et le rang de chaque part ; Mayotte avec ses manques signalés.
- [x] **T4. « Comment » et « Combien ça paie »** (PR #53) — migration 042 : `PART_CONTRATS_COURTS` et
  `PART_TEMPS_PARTIEL` (recensement 2023, jeu Melodi ACT2B, `connecteurs/contrats.py`, par
  sexe et grande tranche d'âge, parts calculées à la lecture, Mayotte absente) ; le salaire
  net moyen de l'appli « vivre » (`SALAIRE_NET_MOYEN`) et le taux de chômage trimestriel
  affichés dans la rubrique par `ref.indicateur_affichage`, sans réimport. Blocs « Les
  emplois sont-ils stables ? » et « Combien ça paie ? » (écart femmes-hommes, âges,
  catégories), cartes `comment` et `salaires`.
  *Critère :* Gironde 15,1 % de contrats courts (50,2 % chez les 15-24 ans), 14,3 % de temps
  partiel ; Paris 3 836 € net par mois en 2024.
- [~] **T5. Télétravail et accidents du travail** — migration 046 :
  `connecteurs/risques_travail.py`. `PART_TELETRAVAIL` (enquête Emploi, jeu Melodi
  `DD_EEC_ANNUEL`, mesure PTREMOTE, France, par grande catégorie ; un seul millésime en ligne) ;
  `ACCIDENTS_TRAVAIL`, `INDICE_FREQUENCE_AT`, `ACCIDENTS_TRAJET`, `MALADIES_PROFESSIONNELLES`
  (Assurance maladie, sinistralité par région administrative, depuis 2005 ; régions = France ;
  Mayotte sans indice). Partie « Au travail » de `/travail` ; la fiche département montre sa
  région. *Critère :* France 19,7 % de télétravail en 2025 (cadres 51,7 %) ; 548 550
  accidents du travail en 2024, 26,4 pour 1 000 salariés (33,2 en 2015) ; Nouvelle-Aquitaine
  32,1, rang 3 sur 17 régions.
- [ ] **T6. Grèves et audience syndicale** — en attente d'une source téléchargeable : le jeu
  ouvert DARES `dares_jint_depuis2005` ne contient plus que les années (vérifié le 24/11/2026),
  l'audience syndicale demande un dépôt manuel.

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
- [x] **S4. VRS sans saisie à la main** (demande de Muthu, 22/11/2026) — migration 039 :
  `vrs.csv` supprimé ; les parts VRS sont lues dans le tableur de la fiche Insee
  « Insécurité, victimation » (France, portrait social, chaque novembre), trouvée par le
  moteur de recherche de l'Insee. Taux de plainte abandonnés : aucune source téléchargeable.
  *Critère :* 2022 = 18, 12, 18 % ; 2024 = 22, 15, 21 % (fiches 8242369 et 8612552).
- [x] **S3. Pages `/securite`** — France (une carte par famille, phrase et courbe ECharts,
  évolution depuis 2016, violences sexuelles, ressenti coupé entre CVS et VRS), fiche
  département (taux, France, rang ; bandeau Paris et départements touristiques), carte par
  famille ; six questions guidées ; accueil, barre latérale, PRD, APP_FLOW, DESIGN et vitrine.
  *Critère :* chaque page s'affiche sans données, avec données, et 404 pour un département ou
  une famille inconnus (`tests/test_securite_pages.py`).

### Appli « Où va l'argent public ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/MmAWsKGAsnpiErF2KEmoRW>.

- [x] **A. France** (PR #42) — migration 033 (rubrique `ARGENT`, sept thèmes, 16 indicateurs, unité
  `milliards_euros`), groupe `demo importer argent` (sept tableaux INSEE des comptes publics et
  dette trimestrielle BDM), page `/argent-public`, accueil, barre latérale, vitrine.
  *Critère :* dépense 2025 = 1 714,1 Md€, déficit −151,6 Md€, dette 3 460,1 Md€ (INSEE) ;
  tests `test_argent_france.py`.
- [x] **B. État** (PR #48) — migration 037 (sources, dimensions `impot_etat` et `mission_etat`, six
  indicateurs, vue `api.repartition_mensuelle`), connecteurs `imports/connecteurs/etat.py`
  (situation mensuelle budgétaire, crédits par mission des PLRG depuis 2023), page
  `/argent-public/etat`. *Critère :* déficit de l'État fin 2025 = 124,2 Md€, fin septembre
  2026 = 159,2 Md€ ; crédits votés 2025 = 582,4 Md€ ; tests `test_argent_etat.py`.
- [~] **C. Local** — migration 044 (source DGFiP, dimension `poste_local`, six indicateurs
  en millions d'euros), connecteurs `imports/connecteurs/collectivites.py` (comptes
  individuels des départements, communes et groupements à fiscalité propre depuis 2016,
  additionnés par département par l'API Opendatasoft, `group_by`), page
  `/argent-public/DEP/{code}` et carte sur `/argent-public`. Postes tirés des comptes
  individuels plutôt que des balances par fonction (5 millions de lignes par an).
  *Critère :* dépenses des départements 2025 = 93 293 M€, des communes 2024 = 124 034 M€ ;
  tests `test_argent_collectivites.py`.
- [ ] **D. Ménage type** — `donnees/baremes.toml`, impôt sur le revenu par département
  (IRCOM), taxe foncière, page `/argent-public/menage`, route `/api/v1/menage-type`.
- [ ] **E. Climat et clôture** — arrêtés de catastrophe naturelle (GASPAR), questions
  guidées restantes, vérification des sept critères du dossier.
- Chaque année : en avril, le PLRG de l'année écoulée paraît ; si une mission est créée ou
  renommée, l'import est rejeté (« Modalité inconnue ») : ajouter la mission dans une
  migration (`mission_etat`) ou son ancien libellé dans `RENOMMEES` (`etat.py`).
- Chaque année : en décembre, quand « Les comptes de la Nation » publie les dépenses par
  fonction, remplacer `EDITIONS_SECOURS` (`imports/connecteurs/comptes_publics.py`) par le
  sommaire de l'édition qui s'achève.

### Appli 5 « Quel avenir pour les Français ? »

Dossier de conception validé le 22/11/2026 : <https://claude.ai/artifact/FTnrnv9wfVht4xEcUs5hnE>.

- [x] **A. Fondations et population** (PR #36) — migration 028 (rubrique `AVENIR`, sept thèmes,
  `ref.scenario`, `stat.projection`, vues `api.projection` et `api.projection_population`),
  groupe `demo importer avenir` (Omphale 2022 : trois scénarios ; France 2026), route
  `/api/v1/projections`, pages `/avenir` et `/avenir/DEP/{code}`, accueil, barre latérale,
  vitrine. *Critère :* Creuse 2018 = estimation INSEE à moins de 1 % ; France 2070 central
  65,9 millions (2026) ; tests `test_avenir_population.py`.
- [x] **B. Climat** (PR #49) — migration 038 (scénarios `GIEC_SSP126/245/585`, 7 indicateurs `CLIM_*`,
  vue `api.projection_climat`), connecteur `climat.py` (Banque mondiale, CMIP6 à 0,25°, sans
  compte : DRIAS demandait une extraction à la main, refusée le 22/11/2026), bloc climat sur
  `/avenir` et la fiche département, sélecteur de scénario (SSP2-4.5 par défaut).
  *Critère :* 96 départements et la métropole ; Bouches-du-Rhône +47 jours à 35 °C ou plus en
  2080-2099 (SSP5-8.5) ; tests `test_avenir_climat.py`.
- [x] **C. Risques naturels** (PR #51) — migration 040 (source `GEORISQUES_GASPAR`, dimension
  `peril_catnat` à six périls, indicateurs `CATNAT_ARRETES`, `CATNAT_SECHERESSE_10ANS`,
  `COMMUNES_PPRN`), connecteur `gaspar.py` (archive gaspar.zip de Géorisques, sans compte ;
  communes ramenées au département ; parts rapportées aux communes du COG 2025,
  `communes_cog.csv` préparé par `outils/communes_cog.py`), bloc « Les catastrophes
  naturelles » sur `/avenir` (France) et la fiche département (France à côté).
  *Critère :* Guéret, 7 reconnaissances dans l'archive du 2/11/2026 (8 sur l'API
  Géorisques, qui a déjà la sécheresse 2025 publiée en février 2026 : l'archive a quelques
  mois de retard) ; Creuse 1 096 reconnaissances depuis 1982 ; tests `test_avenir_risques.py`.
  Les pages `/avenir/theme/{theme}` et leurs classements passent en phase D.
- [~] **D. Questions guidées et clôture** — sans migration. Pages `/avenir/theme/population`
  (évolution depuis 2018, part des 75 ans ou plus, seniors pour 100 actifs ; 2030, 2050,
  2070 ; scénario central), `/avenir/theme/climat` (7 indicateurs × 3 scénarios × 4
  périodes, médiane) et `/avenir/theme/risques` (sécheresse sur dix ans, plans de
  prévention, reconnaissances sur dix ans) : carte colorée, France, plus haut et plus bas,
  classement ; choix par liens, sans JavaScript. Six questions guidées sur `/avenir`, chacune
  vers la carte qui y répond ; liens vers les cartes depuis la fiche. Critères du dossier,
  vérifiés le 24/11/2026 sur les vrais fichiers : 101 fiches en 0,22 s au plus ; population
  2018 à moins de 1 % des estimations (contrôle d'import) ; France 2070 = 65,9 millions
  (Insee Première n° 2108) ; climat : DRIAS remplacé par la Banque mondiale, métropole
  comparée à ses valeurs pour la France (SSP5-8.5, 2080-2099 : +4,40 °C contre +4,43 °C,
  17,8 jours à 35 °C contre 18,3, 44,9 nuits tropicales contre 45,4) ; Guéret : 7
  reconnaissances dans l'archive GASPAR, 8 sur l'API (retard de l'archive) ; source,
  scénario et horizon affichés ; pages lisibles à 390 px sans défilement horizontal. Tests
  `test_avenir_themes.py`.

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
