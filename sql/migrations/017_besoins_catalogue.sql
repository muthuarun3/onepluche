-- Appli 2 « De quoi les Français ont-ils besoin ? », phase A : catalogue étendu.
-- Dossier de conception de l'appli 2, étapes 5 et 6. Rien ne change pour l'appli 1 :
-- ses indicateurs prennent la rubrique QUI, sans thème ni angle.

-- Rubrique, thème et angle de lecture (accès, coût, manque) de chaque indicateur.
ALTER TABLE ref.indicateur
  ADD COLUMN rubrique text NOT NULL DEFAULT 'QUI' CHECK (rubrique IN ('QUI', 'BESOINS')),
  ADD COLUMN theme text CHECK (theme IN ('LOGEMENT', 'ENERGIE', 'EAU', 'ALIMENTATION',
                                         'TRANSPORTS', 'SOINS', 'NUMERIQUE', 'GARDE')),
  ADD COLUMN angle text CHECK (angle IN ('ACCES', 'COUT', 'MANQUE')),
  -- Bornes plausibles : une valeur lue en dehors fait rejeter l'import.
  ADD COLUMN borne_min numeric,
  ADD COLUMN borne_max numeric,
  -- Seuil de variation propre à l'indicateur (prix, médianes) ; NULL = règle générale
  -- (3 % pour les effectifs, aucun contrôle pour le reste).
  ADD COLUMN seuil_variation numeric CHECK (seuil_variation > 0 AND seuil_variation < 1),
  ADD CONSTRAINT indicateur_bornes_check
    CHECK (borne_min IS NULL OR borne_max IS NULL OR borne_min <= borne_max),
  -- Un indicateur de la rubrique « besoins » appartient toujours à un thème.
  ADD CONSTRAINT indicateur_besoins_theme_check
    CHECK ((rubrique = 'BESOINS') = (theme IS NOT NULL)),
  ADD CONSTRAINT indicateur_besoins_angle_check
    CHECK (angle IS NULL OR rubrique = 'BESOINS');

-- Unités des prix, des consommations et des densités.
ALTER TABLE ref.indicateur DROP CONSTRAINT indicateur_unite_check;
ALTER TABLE ref.indicateur ADD CONSTRAINT indicateur_unite_check
  CHECK (unite IN ('personnes', 'pourcentage', 'pour_mille', 'ratio', 'annees',
                   'logements', 'nombre', 'euros', 'euros_m2', 'mwh', 'indice',
                   'consultations_hab', 'pour_10000'));

-- Prix et médianes : ni effectifs, ni taux.
ALTER TABLE ref.indicateur DROP CONSTRAINT indicateur_nature_check;
ALTER TABLE ref.indicateur ADD CONSTRAINT indicateur_nature_check
  CHECK (nature IN ('effectif', 'taux', 'flux', 'ratio', 'prix'));

-- Séries mensuelles (indice des prix ; carburants plus tard).
ALTER TABLE stat.observation DROP CONSTRAINT observation_periode_type_check;
ALTER TABLE stat.observation ADD CONSTRAINT observation_periode_type_check
  CHECK (periode_type IN ('1ER_JANVIER', 'ANNEE', 'TRIMESTRE', 'RP', 'MOIS'));

-- Poids communaux (résidences principales louées, population…) servant à ramener une
-- source communale au département. Zone d'import seulement : jamais publiés.
CREATE TABLE ingest.poids_commune (
  dimension text     NOT NULL CHECK (dimension ~ '^[A-Z][A-Z0-9_]+$'),
  annee     smallint NOT NULL CHECK (annee BETWEEN 1990 AND 2100),
  commune   text     NOT NULL CHECK (commune ~ '^[0-9][0-9AB][0-9]{3}$'),
  poids     numeric  NOT NULL CHECK (poids >= 0),
  import_id integer  NOT NULL REFERENCES ingest.import ON DELETE CASCADE,
  PRIMARY KEY (dimension, annee, commune)
);

-- La vue lue par l'application expose les nouvelles colonnes (ajoutées en fin de vue).
CREATE OR REPLACE VIEW api.indicateur AS
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
        WHERE im.source_id = s.source_id AND im.statut = 'PUBLIE') AS mis_a_jour_le,
       i.rubrique,
       i.theme,
       i.angle,
       i.borne_min,
       i.borne_max
FROM ref.indicateur i
JOIN ref.source s USING (source_id);
