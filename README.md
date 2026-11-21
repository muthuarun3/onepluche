# Démographie France

Application d'exploration et de visualisation des données démographiques françaises,
à partir des sources officielles (INSEE, DREES). Brique d'un écosystème d'applications.

Conception complète (besoin, sources, architecture, schéma, imports, MVP, feuille de route) :
voir le dossier de conception du projet.

**État : phase 0 (fondations).** Base PostgreSQL, rôles, migrations, référentiel
géographique, API minimale, déploiement et sauvegardes. Aucune donnée statistique
importée pour l'instant (phase 1).

## Principes

- Python côté serveur, HTML rendu côté serveur, JavaScript minimal, sans étape de compilation.
- PostgreSQL comme unique stockage. SQL écrit à la main, toujours paramétré.
- Cinq dépendances d'exécution : fastapi, uvicorn, psycopg, jinja2, openpyxl.
- Chaque chiffre affiché indique sa source, son millésime et son statut.

## Organisation

```text
sql/roles.sql            rôles PostgreSQL (à exécuter une fois par un superutilisateur)
sql/migrations/          migrations numérotées, appliquées dans l'ordre, jamais modifiées
src/demographie/
  config.py              variables d'environnement
  db.py                  connexions, une par rôle
  migrations.py          application des migrations
  catalogue/             indicateurs et questions guidées (sans accès base)
  imports/               seul module qui écrit en base (rôle import)
  donnees/               seul module qui lit la base (rôle lecture), SQL dans donnees/sql/
  api/                   routes JSON /api/v1, sans SQL
  web/                   pages HTML, sans SQL
  app.py                 assemblage FastAPI
  cli.py                 commandes demo ...
deploy/                  installation Debian, systemd, Caddy, sauvegarde, test de restauration
tests/                   tests (dont les règles entre modules)
```

## Rôles PostgreSQL

| Rôle | Usage | Droits |
| --- | --- | --- |
| `demo_proprietaire` | Migrations uniquement | Propriétaire des schémas |
| `demo_import` | Imports | Lecture de `ref`, écriture de `ingest` et `stat` |
| `demo_lecture` | Application et API | Lecture seule du schéma `api`, requêtes limitées à 5 s |

## Développement local

Prérequis : Python 3.12 ou plus, [uv](https://docs.astral.sh/uv/), PostgreSQL 15 ou plus.

```bash
uv sync                                   # environnement et dépendances verrouillées
cp .env.exemple .env                      # puis adapter les URL de connexion

# Une fois, en superutilisateur PostgreSQL :
psql -d postgres -f sql/roles.sql
# Définir un mot de passe pour chaque rôle (ALTER ROLE ... PASSWORD ...)
createdb -O demo_proprietaire demographie

set -a; source .env; set +a
uv run demo migrer                        # applique les migrations
uv run demo etat                          # vérifie la base
uv run demo importer estimations          # télécharge et importe les estimations INSEE
uv run demo importer etat-civil           # naissances, décès, fécondité, espérance de vie
uv run demo importer chomage              # taux de chômage localisés, trimestriels
uv run demo importer recensement          # statut d'activité, catégories socioprofessionnelles, secteurs, scolarisation
uv run demo importer retraites            # retraités tous régimes, minimum vieillesse (DREES)
uv run demo importer tout                 # toutes les sources (ce que fait le minuteur hebdomadaire)
uv run demo verifier                      # compare aux chiffres publiés par l'INSEE
uv run uvicorn demographie.app:app --reload
```

Pages : http://localhost:8000/ (choix du territoire), puis `/territoire/DEP/23` par exemple.

## Imports

`demo importer estimations` suit la page stable de l'INSEE vers l'édition en cours,
télécharge les fichiers départemental et régional, conserve le brut sous son empreinte
SHA-256 (`DEMO_DONNEES_BRUTES`), puis contrôle avant de publier :

| Contrôle | En cas d'échec |
| --- | --- |
| Structure du fichier (feuilles, en-têtes de sexe et d'âge) | Rejet |
| Territoire absent du référentiel | Rejet |
| Valeur négative ou en double, taux au-delà de 100 % ou de 1000 ‰ | Rejet |
| Effectifs et flux : somme des tranches d'âge = total ; hommes + femmes = ensemble (à 0,5 %) | Rejet |
| Effectifs et flux : somme des départements (ou régions) = France et France métropolitaine (à 0,5 %) | Rejet |
| Population déjà publiée qui varie de plus de 3 % | Attente : `demo valider <n°>` |

`demo imports` affiche le journal ; la page `/sources` et `GET /api/v1/sources` montrent l'état de chaque fichier. Avec `DEMO_PING_IMPORT` (URL Healthchecks.io, gratuit), chaque import signale son début et son résultat : Healthchecks envoie un courriel si un import est rejeté, attend une validation, ou ne tourne plus. Un fichier déjà publié n'est jamais réimporté ; un
fichier rejeté peut l'être après correction du connecteur. Les révisions de l'INSEE
remplacent les valeurs précédentes. `demo verifier` compare les chiffres servis aux
valeurs du 1er janvier 2026 publiées par l'INSEE (France, Paris, Creuse, Nord, Mayotte) :
après la révision annuelle de janvier, un écart sur ces valeurs provisoires est normal.

Documentation de l'API : http://localhost:8000/api/docs

## Tests

```bash
export DEMO_TEST_ADMIN_URL=postgresql://postgres:motdepasse@localhost:5432/postgres
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

Les tests créent une base temporaire et la suppriment ensuite. Ils (re)créent les rôles
`demo_*` et **changent leur mot de passe** : n'utilisez jamais `DEMO_TEST_ADMIN_URL` sur le
serveur de production. Sans cette variable, les tests qui demandent une base sont ignorés.

## Production

Voir [deploy/README.md](deploy/README.md) : installation sur un VPS Debian 13, HTTPS et accès
protégé par Caddy, sauvegarde quotidienne chiffrée hors site, test de restauration mensuel.

## Données et licence

Données INSEE et DREES sous Licence Ouverte 2.0 (Etalab) : la source et la date de mise à
jour sont citées avec chaque chiffre.
