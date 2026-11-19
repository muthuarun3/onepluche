-- Table de faits unique : une valeur pour un indicateur, un territoire, une période
-- et un croisement sexe x âge x modalité.
CREATE TABLE stat.observation (
  indicateur_id smallint NOT NULL REFERENCES ref.indicateur,
  territoire_id smallint NOT NULL REFERENCES ref.territoire,
  periode       date     NOT NULL,
  periode_type  text     NOT NULL
                CHECK (periode_type IN ('1ER_JANVIER', 'ANNEE', 'TRIMESTRE', 'RP')),
  sexe          char(1)  NOT NULL DEFAULT 'T' CHECK (sexe IN ('F', 'H', 'T')),
  -- Bornes d'âge incluses ; age_max NULL = « et plus » ; les deux NULL = tous âges.
  age_min       smallint CHECK (age_min BETWEEN 0 AND 130),
  age_max       smallint CHECK (age_max BETWEEN 0 AND 130),
  modalite_id   smallint REFERENCES ref.modalite,
  valeur        numeric  NOT NULL,
  statut        text     NOT NULL CHECK (statut IN ('PROVISOIRE', 'DEFINITIF')),
  import_id     integer  NOT NULL REFERENCES ingest.import,
  CHECK (age_max IS NULL OR (age_min IS NOT NULL AND age_max >= age_min)),
  UNIQUE NULLS NOT DISTINCT
    (indicateur_id, territoire_id, periode, sexe, age_min, age_max, modalite_id)
);

-- L'index unique sert « un territoire dans le temps » ;
-- celui-ci sert « tous les territoires à une date » (classements, carte).
CREATE INDEX ON stat.observation (indicateur_id, periode);
CREATE INDEX ON stat.observation (import_id);
