-- Programmes (présidentielle 2027), P2 : veille hebdomadaire des textes des candidats.
-- Dossier de conception : https://claude.ai/artifact/VWJAXgpAa9xJvhY6YLJZmC (étapes 3, 5, 6).
-- Les fiches restent des fichiers du dépôt ; la base ne garde que les relevés : ce qui a été
-- téléchargé, quand, et son empreinte. Une empreinte différente du relevé précédent de la
-- même adresse = le texte a changé, une alerte part. Rien n'est jamais effacé.

CREATE TABLE ingest.programme_releve (
  releve_id     integer     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  election      text        NOT NULL CHECK (election ~ '^[0-9]{4}$'),
  candidat      text        NOT NULL CHECK (candidat ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  version       text        NOT NULL CHECK (version ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  url           text        NOT NULL CHECK (url LIKE 'https://%'),
  releve_le     timestamptz NOT NULL DEFAULT now(),
  -- Téléchargement réussi : statut 200, taille et empreinte ; échec : message, sans empreinte.
  statut_http   smallint,
  taille_octets bigint      CHECK (taille_octets >= 0),
  sha256        char(64)    CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  change        boolean     NOT NULL DEFAULT false,
  message       text,
  CHECK ((sha256 IS NULL) = (taille_octets IS NULL))
);

CREATE INDEX ON ingest.programme_releve (url, releve_le DESC);

COMMENT ON TABLE ingest.programme_releve IS
  'Relevés hebdomadaires des programmes présidentiels suivis (programmes/<élection>/suivis.toml).';

GRANT SELECT, INSERT ON ingest.programme_releve TO demo_import;

-- Dernier relevé de chaque adresse suivie, pour la page « Sources ».
CREATE VIEW api.programme_releve AS
SELECT DISTINCT ON (url)
       election, candidat, version, url, releve_le, statut_http, sha256, change, message,
       (SELECT max(r2.releve_le) FROM ingest.programme_releve r2
        WHERE r2.url = r.url AND r2.change) AS dernier_changement
FROM ingest.programme_releve r
ORDER BY url, releve_le DESC;

GRANT SELECT ON api.programme_releve TO demo_lecture;
