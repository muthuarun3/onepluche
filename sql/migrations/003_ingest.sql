-- Journal des imports : une ligne par fichier téléchargé.
-- Le fichier brut est conservé sur disque sous son empreinte SHA-256.
CREATE TABLE ingest.import (
  import_id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id       smallint    NOT NULL REFERENCES ref.source,
  url             text        NOT NULL,
  fichier_nom     text        NOT NULL,
  sha256          char(64)    NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  taille_octets   bigint      NOT NULL CHECK (taille_octets >= 0),
  millesime       text,
  statut          text        NOT NULL DEFAULT 'EN_COURS'
                  CHECK (statut IN ('EN_COURS', 'REJETE', 'EN_ATTENTE', 'PUBLIE')),
  debut           timestamptz NOT NULL DEFAULT now(),
  fin             timestamptz CHECK (fin >= debut),
  lignes_lues     integer     CHECK (lignes_lues >= 0),
  lignes_chargees integer     CHECK (lignes_chargees >= 0),
  message         text,
  -- Un même fichier d'une même source n'est jamais importé deux fois.
  UNIQUE (source_id, sha256)
);

CREATE INDEX ON ingest.import (source_id, debut DESC);
