-- Phase 1 : estimations de population par sexe et âge (INSEE).
-- Zone de préparation des imports, indicateurs, vue matérialisée de structure par âge,
-- vues de l'application.

-- Les objets créés désormais par le propriétaire reçoivent automatiquement les droits.
ALTER DEFAULT PRIVILEGES IN SCHEMA ingest
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO demo_import;
ALTER DEFAULT PRIVILEGES IN SCHEMA stat
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO demo_import;
ALTER DEFAULT PRIVILEGES IN SCHEMA api
  GRANT SELECT ON TABLES TO demo_lecture;
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Lignes lues d'un fichier, contrôlées avant publication dans stat.observation.
-- Elles restent ici tant que l'import est EN_ATTENTE de validation.
CREATE TABLE ingest.ligne (
  import_id     integer  NOT NULL REFERENCES ingest.import ON DELETE CASCADE,
  indicateur_id smallint NOT NULL REFERENCES ref.indicateur,
  territoire_id smallint NOT NULL REFERENCES ref.territoire,
  periode       date     NOT NULL,
  periode_type  text     NOT NULL,
  sexe          char(1)  NOT NULL,
  age_min       smallint,
  age_max       smallint,
  modalite_id   smallint REFERENCES ref.modalite,
  valeur        numeric  NOT NULL,
  statut        text     NOT NULL,
  -- Faux pour les lignes lues seulement pour les contrôles (ex. total France
  -- d'un fichier régional, déjà publié depuis le fichier départemental).
  a_publier     boolean  NOT NULL
);
CREATE INDEX ON ingest.ligne (import_id);

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       'Les trois dernières années sont provisoires et révisées chaque année par l''INSEE.',
       'Série comparable dans le temps et entre territoires (géographie au 1er janvier 2026).'
FROM ref.source s
CROSS JOIN (VALUES
  ('POP', 'Population',
   'Population estimée au 1er janvier.',
   'personnes', 'effectif', NULL),
  ('PART_MOINS_20', 'Part des moins de 20 ans',
   'Part des personnes de moins de 20 ans dans la population au 1er janvier.',
   'pourcentage', 'taux', '100 × population de 0 à 19 ans / population'),
  ('PART_60_PLUS', 'Part des 60 ans et plus',
   'Part des personnes de 60 ans ou plus dans la population au 1er janvier.',
   'pourcentage', 'taux', '100 × population de 60 ans et plus / population'),
  ('PART_75_PLUS', 'Part des 75 ans et plus',
   'Part des personnes de 75 ans ou plus dans la population au 1er janvier.',
   'pourcentage', 'taux', '100 × population de 75 ans et plus / population'),
  ('INDICE_VIEILLISSEMENT', 'Indice de vieillissement',
   'Nombre de personnes de 65 ans ou plus pour 100 personnes de moins de 20 ans.',
   'ratio', 'ratio', '100 × population de 65 ans et plus / population de 0 à 19 ans')
) AS v (code, libelle, definition, unite, nature, formule)
WHERE s.code = 'INSEE_EST';

-- Agrégats par âge, recalculés après chaque publication.
CREATE MATERIALIZED VIEW stat.structure_age AS
SELECT o.territoire_id,
       o.periode,
       sum(o.valeur) FILTER (WHERE o.age_min IS NULL AND o.age_max IS NULL) AS population,
       sum(o.valeur) FILTER (WHERE o.age_max <= 19) AS moins_20,
       sum(o.valeur) FILTER (WHERE o.age_min >= 60) AS plus_60,
       sum(o.valeur) FILTER (WHERE o.age_min >= 65) AS plus_65,
       sum(o.valeur) FILTER (WHERE o.age_min >= 75) AS plus_75,
       bool_or(o.statut = 'PROVISOIRE') AS provisoire
FROM stat.observation o
JOIN ref.indicateur i USING (indicateur_id)
WHERE i.code = 'POP' AND o.sexe = 'T' AND o.modalite_id IS NULL
GROUP BY o.territoire_id, o.periode;

CREATE UNIQUE INDEX ON stat.structure_age (territoire_id, periode);

-- Le rôle d'import n'est pas propriétaire de la vue : il passe par cette fonction.
CREATE FUNCTION stat.rafraichir_vues() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY stat.structure_age;
END
$$;
REVOKE EXECUTE ON FUNCTION stat.rafraichir_vues() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION stat.rafraichir_vues() TO demo_import;

-- Vues de l'application.
CREATE VIEW api.indicateur AS
SELECT i.code,
       i.libelle,
       i.definition,
       i.unite,
       i.nature,
       i.formule,
       i.avertissement,
       i.comparabilite,
       s.code    AS source_code,
       s.libelle AS source_libelle,
       s.url     AS source_url,
       s.licence AS source_licence,
       (SELECT max(im.fin) FROM ingest.import im
        WHERE im.source_id = s.source_id AND im.statut = 'PUBLIE') AS mis_a_jour_le
FROM ref.indicateur i
JOIN ref.source s USING (source_id);

CREATE VIEW api.serie AS
SELECT v.indicateur,
       t.niveau,
       t.code,
       extract(year FROM s.periode)::int AS annee,
       v.valeur,
       s.provisoire
FROM stat.structure_age s
JOIN ref.territoire t USING (territoire_id)
CROSS JOIN LATERAL (VALUES
  ('POP', s.population),
  ('PART_MOINS_20', round(100 * s.moins_20 / nullif(s.population, 0), 2)),
  ('PART_60_PLUS', round(100 * s.plus_60 / nullif(s.population, 0), 2)),
  ('PART_75_PLUS', round(100 * s.plus_75 / nullif(s.population, 0), 2)),
  ('INDICE_VIEILLISSEMENT', round(100 * s.plus_65 / nullif(s.moins_20, 0), 1))
) AS v (indicateur, valeur)
WHERE v.valeur IS NOT NULL;

CREATE VIEW api.structure AS
SELECT t.niveau,
       t.code,
       extract(year FROM o.periode)::int AS annee,
       o.sexe,
       o.age_min,
       o.age_max,
       o.valeur,
       o.statut = 'PROVISOIRE' AS provisoire
FROM stat.observation o
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
WHERE i.code = 'POP'
  AND o.sexe IN ('F', 'H')
  AND o.age_min IS NOT NULL
  AND o.modalite_id IS NULL;

-- Droits explicites sur ce qui a été créé avant les privilèges par défaut ci-dessus
-- (sans effet si déjà accordés).
GRANT SELECT, INSERT, UPDATE, DELETE ON ingest.ligne TO demo_import;
GRANT SELECT ON api.indicateur, api.serie, api.structure TO demo_lecture;
