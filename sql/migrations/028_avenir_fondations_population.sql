-- Appli 5 « Quel avenir pour les Français ? » (rubrique /avenir), phase A : fondations et
-- population. Dossier de conception de l'appli 5, étapes 3 et 5 (validées le 22/11/2026).
--
-- Les projections ont deux dimensions que les observations n'ont pas : un scénario
-- (central, population basse, RCP 8.5…) et une statistique d'ensemble (médiane et
-- fourchette des modèles climatiques). Elles vont dans leur propre table, stat.projection,
-- pour qu'un chiffre de 2050 ne soit jamais lu comme un chiffre observé.

-- Rubrique AVENIR et ses sept thèmes (dossier de conception, étape 1).
INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire, avec_angles)
VALUES ('AVENIR', 'Quel avenir pour les Français ?', '/avenir',
        7, true, false);

INSERT INTO ref.theme (rubrique, code, libelle, ordre) VALUES
  ('AVENIR', 'POPULATION', 'Population', 1),
  ('AVENIR', 'CLIMAT', 'Climat', 2),
  ('AVENIR', 'RISQUES', 'Risques naturels', 3),
  ('AVENIR', 'EAU', 'Eau', 4),
  ('AVENIR', 'AGRICULTURE', 'Agriculture', 5),
  ('AVENIR', 'SANTE', 'Santé future', 6),
  ('AVENIR', 'EMPLOI', 'Emploi futur', 7);

-- Scénarios des producteurs, avec leur libellé affiché.
CREATE TABLE ref.scenario (
  scenario_id     smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code            text     NOT NULL UNIQUE CHECK (code ~ '^[A-Z][A-Z0-9_]+$'),
  libelle         text     NOT NULL CHECK (libelle <> ''),
  famille         text     NOT NULL
                  CHECK (famille IN ('INSEE', 'GIEC', 'NIVEAU_RECHAUFFEMENT', 'REFERENCE')),
  description     text     NOT NULL,
  -- Réchauffement mondial correspondant, au sens du GIEC (scénarios climatiques).
  equivalent_giec text,
  ordre           smallint NOT NULL
);

INSERT INTO ref.scenario (code, libelle, famille, description, ordre) VALUES
  ('INSEE_CENTRAL', 'Scénario central', 'INSEE',
   'Les tendances récentes de fécondité, d''espérance de vie et de migrations se prolongent.', 1),
  ('INSEE_POP_BASSE', 'Population basse', 'INSEE',
   'Fécondité, espérance de vie et solde migratoire bas : la fourchette basse de l''INSEE.', 2),
  ('INSEE_POP_HAUTE', 'Population haute', 'INSEE',
   'Fécondité, espérance de vie et solde migratoire hauts : la fourchette haute de l''INSEE.', 3);

GRANT SELECT ON ref.scenario TO demo_import;

-- Table de faits des projections. periode : 1er janvier de l'année projetée (population)
-- ou début de la période ; periode_fin : fin d'une période (flux annuel, moyenne sur
-- 30 ans), NULL pour une date.
CREATE TABLE stat.projection (
  indicateur_id smallint NOT NULL REFERENCES ref.indicateur,
  territoire_id smallint NOT NULL REFERENCES ref.territoire,
  scenario_id   smallint NOT NULL REFERENCES ref.scenario,
  periode       date     NOT NULL,
  periode_fin   date     CHECK (periode_fin >= periode),
  sexe          char(1)  NOT NULL DEFAULT 'T' CHECK (sexe IN ('F', 'H', 'T')),
  age_min       smallint CHECK (age_min BETWEEN 0 AND 130),
  age_max       smallint CHECK (age_max BETWEEN 0 AND 130),
  -- VALEUR : chiffre publié tel quel ; MEDIANE, BAS, HAUT : ensemble de modèles.
  statistique   text     NOT NULL DEFAULT 'VALEUR'
                CHECK (statistique IN ('VALEUR', 'MEDIANE', 'BAS', 'HAUT')),
  valeur        numeric  NOT NULL,
  import_id     integer  NOT NULL REFERENCES ingest.import,
  CHECK (age_max IS NULL OR (age_min IS NOT NULL AND age_max >= age_min)),
  UNIQUE NULLS NOT DISTINCT (indicateur_id, territoire_id, scenario_id, periode, periode_fin,
                             sexe, age_min, age_max, statistique)
);
CREATE INDEX ON stat.projection (indicateur_id, scenario_id, periode);
CREATE INDEX ON stat.projection (import_id);

-- Lignes lues d'un fichier de projections, contrôlées avant publication.
CREATE TABLE ingest.ligne_projection (
  import_id     integer  NOT NULL REFERENCES ingest.import ON DELETE CASCADE,
  indicateur_id smallint NOT NULL REFERENCES ref.indicateur,
  territoire_id smallint NOT NULL REFERENCES ref.territoire,
  scenario_id   smallint NOT NULL REFERENCES ref.scenario,
  periode       date     NOT NULL,
  periode_fin   date,
  sexe          char(1)  NOT NULL,
  age_min       smallint,
  age_max       smallint,
  statistique   text     NOT NULL,
  valeur        numeric  NOT NULL
);
CREATE INDEX ON ingest.ligne_projection (import_id);

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_OMPHALE', 'INSEE',
   'Projections de population 2018-2070 pour les départements (Omphale 2022)',
   'https://www.insee.fr/fr/statistiques/7747107'),
  ('INSEE_PROJ_FR', 'INSEE',
   'Projections de population à l''horizon 2070 pour la France (2026)',
   'https://www.insee.fr/fr/statistiques/9004289');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme,
                            borne_min, borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'AVENIR', 'POPULATION', v.borne_min, v.borne_max
FROM (VALUES
  ('PROJ_POP', 'INSEE_OMPHALE', 'Population projetée',
   'Population au 1er janvier de l''année projetée, par sexe et âge quinquennal, selon le '
   'scénario choisi. Projections départementales Omphale 2022, à partir du recensement 2018.',
   'personnes', 'effectif', NULL,
   'Une projection n''est pas une prévision : elle dit ce qui arriverait si les hypothèses '
   'se réalisaient. Ces projections départementales datent de 2022 ; les projections '
   'nationales de 2026 prévoient moins d''habitants (65,9 millions en 2070 au lieu de 68,1).',
   'Les départements se comparent entre eux et avec la France (somme des départements), '
   'dans le même scénario. Ne pas comparer avec les projections nationales de 2026.',
   0, 80000000),
  ('PROJ_SOLDE_NATUREL', 'INSEE_OMPHALE', 'Solde naturel projeté',
   'Naissances moins décès pendant l''année projetée, selon le scénario choisi.',
   'personnes', 'flux', 'Naissances - décès',
   'Une projection n''est pas une prévision.',
   'Comparable entre départements dans le même scénario.', -1000000, 1000000),
  ('PROJ_SOLDE_MIGRATOIRE', 'INSEE_OMPHALE', 'Solde migratoire projeté',
   'Arrivées moins départs pendant l''année projetée (autres départements et étranger), '
   'selon le scénario choisi.',
   'personnes', 'flux', 'Entrées - sorties',
   'Une projection n''est pas une prévision.',
   'Comparable entre départements dans le même scénario.', -1000000, 1000000),
  ('PROJ_POP_FRANCE', 'INSEE_PROJ_FR', 'Population projetée de la France (projections 2026)',
   'Population de la France au 1er janvier selon les projections nationales publiées par '
   'l''INSEE en juin 2026, par grand groupe d''âge pour le scénario central.',
   'personnes', 'effectif', NULL,
   'Une projection n''est pas une prévision. Valeurs arrondies au millier.',
   'Plus récentes que les projections départementales (2022) : ne pas additionner ni '
   'comparer directement les deux.', 0, 80000000)
) AS v (code, source, libelle, definition, unite, nature, formule, avertissement,
        comparabilite, borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;

-- Vues lues par l'application.
CREATE VIEW api.scenario AS
SELECT code, libelle, famille, description, equivalent_giec, ordre
FROM ref.scenario;

CREATE VIEW api.projection AS
SELECT i.code AS indicateur,
       t.niveau,
       t.code,
       sc.code AS scenario,
       extract(year FROM p.periode)::int AS annee,
       p.periode,
       p.periode_fin,
       p.sexe,
       p.age_min,
       p.age_max,
       p.statistique,
       p.valeur
FROM stat.projection p
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
JOIN ref.scenario sc USING (scenario_id);

-- Synthèse par territoire, scénario et année de la population projetée (Omphale) :
-- population, parts des moins de 20 ans et des 75 ans ou plus, et 65 ans ou plus pour
-- 100 personnes de 20 à 64 ans.
CREATE VIEW api.projection_population AS
SELECT t.niveau,
       t.code,
       sc.code AS scenario,
       extract(year FROM p.periode)::int AS annee,
       sum(p.valeur) FILTER (WHERE p.age_min IS NULL) AS population,
       round(100 * sum(p.valeur) FILTER (WHERE p.age_max <= 19)
             / nullif(sum(p.valeur) FILTER (WHERE p.age_min IS NULL), 0), 2) AS part_moins_20,
       round(100 * sum(p.valeur) FILTER (WHERE p.age_min >= 75)
             / nullif(sum(p.valeur) FILTER (WHERE p.age_min IS NULL), 0), 2) AS part_75_plus,
       round(100 * sum(p.valeur) FILTER (WHERE p.age_min >= 65)
             / nullif(sum(p.valeur) FILTER (WHERE p.age_min >= 20 AND p.age_max <= 64), 0),
             1) AS seniors_pour_100_actifs
FROM stat.projection p
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
JOIN ref.scenario sc USING (scenario_id)
WHERE i.code = 'PROJ_POP' AND p.sexe = 'T' AND p.statistique = 'VALEUR'
GROUP BY t.niveau, t.code, sc.code, p.periode;
