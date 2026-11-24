# TRD — Document d'exigences techniques

**État au :** 22 novembre 2026. Ce document fixe la pile et l'architecture. Une
bibliothèque, un service ou un langage qui n'y figure pas n'est pas ajouté sans l'accord de
Muthu.

## 1. Principes

- **Monolithe modulaire** : un seul paquet Python, un seul processus web, un seul serveur.
- **PostgreSQL est l'unique stockage.** Pas de cache séparé, pas de file de messages, pas
  d'orchestrateur, pas de stockage objet applicatif.
- **HTML rendu côté serveur**, JavaScript minimal, **aucune étape de compilation**.
- **SQL écrit à la main**, dans des fichiers `.sql`, toujours paramétré.
- **Aucun modèle de langage**, aucune clé d'API tierce : toutes les sources sont publiques
  et sans compte.
- **Sobriété** : chaque dépendance est justifiée ; budget total sous 10 € par mois.

## 2. Pile technique

| Couche | Choix | Ce qui est exclu |
| --- | --- | --- |
| Langage serveur | Python 3.12 ou plus | TypeScript, Node côté serveur |
| Web et API | FastAPI + Uvicorn | Django, Flask, Next.js |
| Accès base | psycopg 3 (`psycopg[binary]`), SQL en fichiers | ORM (SQLAlchemy), Supabase, Prisma |
| Migrations | Fichiers SQL numérotés `sql/migrations/NNN_*.sql` + `demo migrer` | Alembic |
| Gabarits | Jinja2 | React, Svelte, Vue, toute application monopage |
| Interactivité | JavaScript natif servi tel quel (`static/app.js`) | htmx, Alpine, npm, bundler |
| Graphiques | Apache ECharts, fichier local `static/echarts.min.js` | Chart.js, D3, Leaflet, tuiles externes |
| Carte de choix du territoire | SVG dessiné par le serveur (`web/carte.py`, `templates/_carte.html`), un lien par territoire, sans JavaScript | ECharts pour ce choix (1 Mo de script pour une page de liens) |
| Fond de carte | Contours IGN Admin Express COG simplifiés (via france-geojson, Licence ouverte), projetés et versionnés dans `web/contours.json` (36 Ko, 12 Ko compressé) ; régénérés par `outils/contours_svg.py` | PostGIS |
| Lecture XLSX | openpyxl | pandas, polars |
| Lecture Parquet | pyarrow, par paquets et colonnes utiles (résultats des élections, 232 Mo au lieu de 2,8 Go en CSV) | pandas, polars, duckdb |
| XML sûr | defusedxml | lxml |
| Base | PostgreSQL 17 (paquet Debian ; 15 minimum, pour `NULLS NOT DISTINCT`) | Base managée |
| Authentification | `basicauth` de Caddy, un identifiant par personne | Clerk, Auth0, table de comptes |
| Outillage | uv (verrouillage `uv.lock`), pytest, ruff, httpx (tests) | Poetry, pip-tools |
| Intégration continue | GitHub Actions (lint, format, `bash -n`, tests avec PostgreSQL 17) | — |
| Mises à jour | Dependabot | — |
| Serveur | VPS netcup, Debian 13, 2 vCPU, 4 Go, 80 Go | PaaS, Docker en production |
| Proxy et HTTPS | Caddy (certificats automatiques) | Nginx + certbot |
| Planification | Minuteurs systemd | cron, Celery, Airflow |
| Sauvegarde | `pg_dump` chiffré GPG (AES-256) + rclone | Sauvegarde du fournisseur seule |
| Supervision des imports | Healthchecks.io (gratuit, facultatif) | — |
| Domaine | `onepluche.duckdns.org` (DuckDNS, gratuit) | — |

**Dépendances d'exécution (7) :** fastapi, uvicorn, psycopg, jinja2, openpyxl, defusedxml, pyarrow.
**Bibliothèque JavaScript (1) :** ECharts.

## 3. Architecture

```text
Sources officielles ──► imports (rôle demo_import) ──► PostgreSQL : ref, ingest, stat
                                                             │ vues du schéma api
                                                             ▼
             navigateur ◄── web (Jinja2) ◄── donnees (rôle demo_lecture) ──► api (/api/v1, JSON)
                                    ▲
                     Caddy (HTTPS, identifiants) ◄── Internet
```

### Modules du paquet `src/demographie/`

| Module | Responsabilité | Peut importer | Ne doit jamais |
| --- | --- | --- | --- |
| `catalogue/` | Indicateurs, valeurs de référence, questions guidées (données pures) | rien | toucher la base |
| `imports/` | Faire entrer les données : connecteurs, pipeline, contrôles | catalogue, db, config | être appelé par le web |
| `donnees/` | Toutes les lectures ; SQL dans `donnees/sql/` | catalogue, db | écrire |
| `api/` | Routes JSON `/api/v1` | donnees, catalogue | contenir du SQL |
| `web/` | Pages HTML, gabarits, statiques | donnees, catalogue | contenir du SQL, appeler l'API par HTTP |
| `app.py` | Assemblage FastAPI, en-têtes de sécurité, `/sante` | tout | — |
| `cli.py` | Commandes `demo …` | tout | — |

Ces règles sont vérifiées par `tests/test_architecture.py` : une violation fait échouer la CI.

### Une rubrique par application

Les applications partagent le même code, la même base et le même serveur. Chacune est une
**rubrique** : des pages sous son préfixe (`/francais`, `/besoins`), ses indicateurs marqués
dans `ref.indicateur.rubrique` (`QUI`, `BESOINS`), ses connecteurs regroupés sous un nom
(`demo importer logement`). Une nouvelle application suit le même modèle : sa migration
ajoute une ligne dans `ref.rubrique`, ses thèmes dans `ref.theme` et ses unités nouvelles
dans `ref.unite` (migration 026), sans réécrire de contrainte ni toucher à l'API, qui lit
ces tables pour valider ses filtres.

## 4. Imports

Un **pipeline commun** (`imports/pipeline.py`) et **un connecteur par source**
(`imports/connecteurs/`). Un connecteur dit où est le fichier, le lit et le traduit en
lignes ; le pipeline fait le reste.

1. **Détecter et télécharger.** Le fichier brut est enregistré sous son empreinte SHA-256
   dans `DEMO_DONNEES_BRUTES`. Empreinte déjà connue : arrêt. Une réponse d'API est d'abord
   enregistrée en fichier, puis traitée comme un fichier.
2. **Lire** vers `ingest.ligne`, codes de territoire, sexe et bornes d'âge normalisés.
3. **Contrôler** (fichiers `imports/sql/controle_*.sql`) :

   | Contrôle | Échec |
   | --- | --- |
   | Structure du fichier, territoires connus | Rejet |
   | Doublons, valeurs négatives, taux hors bornes | Rejet |
   | Sommes : tranches = total, hommes + femmes = ensemble, départements = France (0,5 %, réglable par connecteur) | Rejet |
   | Bornes plausibles par indicateur (`borne_min`, `borne_max`) | Rejet |
   | Couverture : au moins 100 départements, sauf absences déclarées par le connecteur | Rejet |
   | Variation par rapport à la valeur publiée : 3 % (effectifs), seuil propre à l'indicateur (15 % pour les prix) | Attente de `demo valider` |

4. **Publier** en une transaction dans `stat.observation`, puis rafraîchir les vues
   matérialisées. Un échec laisse les données en place intactes.

Règles : les révisions remplacent les valeurs précédentes (pas d'historique) ; les sources
communales sont ramenées au département dans le connecteur (poids dans
`ingest.poids_commune`) ; les gros fichiers sont lus en flux ; Melodi au plus une requête
toutes les 2 secondes ; l'API INSEE « Données locales » (arrêtée le 1/12/2026) n'est jamais
utilisée.

### Connecteurs en service

| Groupe (`demo importer …`) | Sources |
| --- | --- |
| `estimations` | INSEE, estimations de population, départements et régions (XLSX) |
| `etat-civil` | INSEE Melodi, naissances et décès |
| `chomage` | INSEE BDM, taux de chômage localisés (SDMX) |
| `recensement` | INSEE Melodi, activité, catégories socioprofessionnelles, secteurs, scolarisation |
| `retraites` | DREES, retraités tous régimes et pension moyenne de droit direct (EACR), minimum vieillesse |
| `etudiants` | Ministère de l'Enseignement supérieur (Opendatasoft), formations et disciplines |
| `sante` | Assurance maladie (data.ameli), cartographie des pathologies |
| `logement` | INSEE Melodi, logements, statut d'occupation, chauffage, poids communaux ; Filosofi niveau de vie et pauvreté ; ANIL Carte des loyers ; DGFiP DVF ; SDES RPLS |
| `energie` | Agence ORE, consommations résidentielles ; ADEME, DPE ; INSEE BDM, indice des prix |
| `budget` | INSEE Melodi, comptes nationaux : dépense des ménages par poste, dépenses pré-engagées |
| `transports` | Ministère de l'Économie, prix des carburants déclarés par les stations (moyennes par département calculées par l'API Opendatasoft, un relevé par mois) ; INSEE Melodi, trajets domicile-travail et voitures des ménages (recensement), dépense en carburants (comptes nationaux) |
| `soins` | DREES, accessibilité aux médecins généralistes (APL) ; Assurance maladie, ALD sans médecin traitant ; INSEE Melodi, équipements de santé (BPE) |
| `avenir` | INSEE, projections de population par département 2018-2070 (Omphale 2022 : scénarios central, population basse, population haute ; XLSX) et pour la France (2026, Insee Première n° 2108). Contrôles propres : 101 départements, population de 2018 à moins de 1 % des estimations, fourchette basse ≤ centrale ≤ haute ; publication dans `stat.projection` ; climat : Banque mondiale (Climate Change Knowledge Portal), modèles CMIP6 du GIEC à 0,25°, écarts à 1995-2014 de 7 indicateurs × 3 scénarios SSP × 4 périodes × 3 statistiques (10e centile, médiane, 90e). NetCDF classique lu sans dépendance (`imports/netcdf3.py`), seules les lignes de la métropole téléchargées (requêtes HTTP Range) ; moyenne de chaque département pondérée par sa surface dans chaque maille (`mailles_climat.csv`, préparé par `outils/mailles_climat.py`) ; relu seulement quand le millésime change ; risques naturels : base GASPAR de Géorisques (gaspar.zip mensuelle, fichiers catnat et pprn lus en flux), reconnaissances de catastrophe naturelle par année et par péril, parts de communes (sécheresse sur 10 ans, plans de prévention) rapportées au COG 2025 (`communes_cog.csv`, `outils/communes_cog.py`) ; zéros publiés pour tous les départements |
| `securite` | Ministère de l'Intérieur : SSMSI, délinquance enregistrée par département (CSV data.gouv.fr, édition de juillet) ; ONISR, accidents corporels de la route (deux fichiers BAAC par an, rangés dans une archive zip) ; enquêtes de victimation CVS (cube data.gouv.fr) et VRS (tableur de la fiche Insee « Insécurité, victimation », France, portrait social, trouvée chaque novembre par le moteur de recherche de l'Insee) |
| `vivre` | INSEE Melodi : Filosofi détaillé (déciles, Gini, D9/D1, S80/S20, décomposition du revenu disponible ; 2023, métropole et La Réunion ; impôts rangés en positif) ; Base Tous salariés, salaire net mensuel moyen en équivalent temps plein du privé, par sexe × catégorie et par sexe × âge (2023-2024, 101 départements) ; séries nationales : salaire moyen du privé en euros constants depuis 1996, enquête Revenus fiscaux et sociaux rétropolée (France métropolitaine, 1996-2024), comptes des ménages (`DD_CNA_AGREGATS`, un fichier par agrégat, années provisoires signalées), patrimoine (`DS_ENQPAT_DET`, 2024, France hors Mayotte rangée sous `FR`, trois ventilations demandées à part ; `DD_CNA_PATRIMOINE`, placements financiers) |
| `travail` | INSEE BDM, cinq jeux filtrés par clé SDMX (sans clé, réponse refusée car trop volumineuse) : chômage annuel par sexe et âge, emploi salarié par secteur et intérim, emploi total, créations et défaillances d'entreprises ; DARES, demandeurs d'emploi trimestriels par département (export CSV de l'API Opendatasoft) ; France Travail, enquête BMO (xlsx trouvés sur data.gouv.fr, bassins additionnés par département, « * » compté zéro) ; INSEE Melodi, recensement : contrats courts et temps partiel (parts calculées à la lecture) |

| `argent` | INSEE, comptes nationaux annuels des administrations publiques (base 2020) : sept tableaux XLSX de « Les comptes de la Nation » (3.101 dette, 3.106 solde, 3.201 recettes par nature et intérêts, 3.215 dépenses et recettes, 3.216 prélèvements obligatoires, 3.301 dépenses par fonction, 3.307 par sous-secteur), trouvés depuis la page stable par le lien « Chiffres détaillés » puis le titre de chaque page ; dépenses par fonction lues dans l'édition précédente jusqu'en décembre (`EDITIONS_SECOURS`). INSEE BDM, dette trimestrielle (SDMX). Le jeu Melodi DD_CNA_APU n'est pas utilisé (totaux non consolidés, pas de fonctions) ; ministère de l'Économie (data.economie.gouv.fr) : situation mensuelle budgétaire de l'État (export JSON) et crédits par mission des PLRG, annexe 1 « Etat_CP », trouvés dans le catalogue par le titre de la pièce jointe (un jeu par année) ; DGFiP, comptes individuels des départements, des communes et des groupements à fiscalité propre (un jeu par année ou paire d'années depuis 2016), additionnés par département et par année côté serveur (export JSON Opendatasoft avec `group_by`) : quelques centaines de lignes au lieu de 35 000 communes ; codes « 001 », « 02A », « 101 » à « 106 » ramenés au code officiel ; code de groupement « 161 » écarté (hors code géographique, quelques millions d'euros) |
| `votes` | Ministère de l'Intérieur, via data.gouv.fr (« données des élections agrégées ») : deux fichiers Parquet par bureau de vote, « Résultats généraux » et « Résultats par candidat », lus par paquets (pyarrow, colonnes utiles des 20 tours seulement) et additionnés par département, Français de l'étranger (`HORS_DEP/ZZ`) et collectivités d'outre-mer (`HORS_DEP/COM`). Date de mise à jour de data.gouv.fr comparée avant téléchargement (`saute_si_millesime_connu`). Choix (candidats, listes, nuances des législatives avec les libellés des circulaires) déclarés par `ref.ajouter_choix` avant le chargement. Contrôles propres : inscrits = abstentions + votants, votants = blancs + nuls + exprimés, 101 départements aux premiers tours ; nuance inconnue = rejet ; Répertoire national des élus (data.gouv.fr, un CSV par mandat retrouvé par son titre, adresse changeante) : maires, conseillers départementaux, députés, sénateurs comptés par territoire, sexe, tranche d'âge et groupe socioprofessionnel, âge médian ; Collectivité européenne d'Alsace répartie par canton ; noms jamais lus au-delà du connecteur |

`demo importer tout` lance l'ensemble, dans cet ordre (estimations d'abord).

## 5. API v1

Contrat pour l'écosystème : une route existante ne change jamais de forme ; on ajoute.

| Route | Rôle | État |
| --- | --- | --- |
| `GET /api/v1/territoires?niveau=` | Territoires et rattachement | En service |
| `GET /api/v1/indicateurs` | Catalogue : définition, unité, source, avertissements, rubrique, thème, angle | En service |
| `GET /api/v1/series?indicateur=&niveau=&code=&debut=&fin=&sexe=` | Série temporelle, statut par point | En service |
| `GET /api/v1/structure?niveau=&code=&annee=` | Pyramide des âges | En service |
| `GET /api/v1/repartition?indicateur=&niveau=&code=&annee=` | Répartition par modalité avec total | En service |
| `GET /api/v1/sources` | État des imports par fichier | En service |
| `GET /api/v1/indicateurs?rubrique=&theme=` | Filtres par rubrique et thème (codes de `ref.rubrique`, `ref.theme` ; inconnu = 422) | En service |
| `GET /api/v1/fiche?niveau=&code=&rubrique=&theme=` | Dernière valeur par indicateur, valeur France de la même période (FR, sinon FM), source ; tri par thème puis accès, coût, manque | En service |
| `GET /api/v1/projections?indicateur=&niveau=&code=&scenario=&sexe=&par_age=` | Valeurs projetées d'un indicateur de la rubrique AVENIR, par scénario (tous si absent) ; scénarios décrits ; inconnu = 404 | En service |
| `GET /api/v1/classement?indicateur=&niveau=&periode=` | Tous les territoires d'un niveau, triés | Prévu |

Paramètres validés par FastAPI (motifs `^[0-9A-Z]{2,3}$`, `^[A-Z][A-Z0-9_]+$`, années
1900-2100) ; rubriques et thèmes vérifiés contre la base. Documentation générée sur `/api/docs`.

## 6. Sécurité

- **Accès** : Caddy `basicauth`, HTTPS obligatoire (HSTS), un identifiant par personne dans
  `/etc/caddy/demographie-utilisateurs`. L'application elle-même n'a pas de comptes.
- **Base** : n'écoute que sur la machine locale ; trois rôles séparés (voir
  [SCHEMA.md](SCHEMA.md)) ; le rôle de l'application ne lit que le schéma `api`, en lecture
  seule, avec un délai maximal de 5 secondes.
- **Requêtes** : uniquement paramétrées ; aucun SQL construit à partir d'une saisie.
- **En-têtes** : CSP `default-src 'self'` (scripts servis par l'appli uniquement), `nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Permissions-Policy` restrictive.
- **Serveur** : SSH par clé uniquement, root SSH désactivé, pare-feu (SSH, 80, 443), mises à
  jour de sécurité automatiques, utilisateur système `demographie` sans shell.
- **Secrets** : variables d'environnement dans `/etc/demographie/env` (production) ou `.env`
  (local, jamais versionné). Rien dans le dépôt.

## 7. Configuration

| Variable | Usage |
| --- | --- |
| `DEMO_DB_PROPRIETAIRE_URL` | Migrations uniquement |
| `DEMO_DB_IMPORT_URL` | Imports |
| `DEMO_DB_LECTURE_URL` | Application web et API |
| `DEMO_DONNEES_BRUTES` | Dossier des fichiers bruts (par empreinte) |
| `DEMO_PING_IMPORT` | URL Healthchecks.io, facultative |

## 8. Déploiement et exploitation

| Élément | Détail |
| --- | --- |
| Installation | `deploy/installer.sh <domaine> <dépôt> <destination rclone>` : PostgreSQL, Caddy, rclone, pare-feu, rôles, migrations, services ; relancé à chaque mise à jour (redémarre l'appli) |
| Services systemd | `demographie-web` (Uvicorn sur 127.0.0.1:8000) |
| Minuteurs | imports le lundi à 6 h 15 ; sauvegarde chaque nuit à 3 h 30 ; restauration testée le 1er du mois à 5 h (heure de Paris) |
| Sauvegarde | base chiffrée + fichiers bruts, 30 jours de rétention, vers `sauvegardes:/var/backups/demographie` |
| Mise à jour | `git pull` dans `/opt/demographie/app`, puis l'installeur, puis `demo importer tout` si une source est ajoutée |
| Accès au serveur | Muthu exécute lui-même les commandes (Termius sur téléphone) ; toujours lui donner des commandes complètes, une par bloc |

Détail : [deploy/README.md](../deploy/README.md).

## 9. Qualité et tests

- `uv run ruff check .` et `uv run ruff format --check .` (lignes de 100 caractères).
- `uv run pytest` : base temporaire créée et supprimée (`DEMO_TEST_ADMIN_URL`), extraits
  réduits des vrais fichiers dans `tests/fixtures/` (scripts `reduire_*.py`), aucun accès
  réseau en CI.
- Chaque connecteur a ses tests de lecture et de rejet ; chaque source a au moins une valeur
  vérifiée contre le site du producteur (`demo verifier`).
- Pas de tests de bout en bout dans un navigateur : les routes HTML sont testées par le
  client de test FastAPI.

## 10. Conventions

- Nommage métier en français (indicateur, territoire, millésime, modalité).
- Une migration ne se modifie jamais une fois fusionnée : on en ajoute une. Numéros suivis,
  pris au moment de la PR. `api.serie` est redéfinie en entier à chaque ajout (colonnes
  nouvelles en fin de vue).
- Ajouter un indicateur : une ligne dans une migration (`ref.indicateur`) et, si besoin, un
  connecteur. Le schéma ne change pas.
- Une PR par tâche, vers `main`, jamais empilée ; titre et description en français.
