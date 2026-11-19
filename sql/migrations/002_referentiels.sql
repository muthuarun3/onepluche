-- Référentiel géographique : France, France métropolitaine, régions, départements.
CREATE TABLE ref.territoire (
  territoire_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  niveau        text     NOT NULL CHECK (niveau IN ('FRANCE', 'REG', 'DEP')),
  code          text     NOT NULL CHECK (code ~ '^[0-9A-Z]{2,3}$'),
  libelle       text     NOT NULL CHECK (libelle <> ''),
  parent_id     smallint REFERENCES ref.territoire,
  cog_millesime smallint NOT NULL CHECK (cog_millesime BETWEEN 2003 AND 2100),
  UNIQUE (niveau, code),
  -- Seule la France entière n'a pas de parent.
  CHECK ((niveau = 'FRANCE' AND code = 'FR') = (parent_id IS NULL))
);

COMMENT ON TABLE ref.territoire IS
  'Territoires de diffusion. Codes du code officiel géographique (COG) de l''INSEE.';

-- Producteurs et jeux de données.
CREATE TABLE ref.source (
  source_id  smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code       text NOT NULL UNIQUE CHECK (code ~ '^[A-Z][A-Z0-9_]+$'),
  producteur text NOT NULL,
  libelle    text NOT NULL,
  url        text NOT NULL CHECK (url LIKE 'https://%'),
  licence    text NOT NULL DEFAULT 'Licence Ouverte 2.0 (Etalab)'
);

-- Catalogue des indicateurs : la définition est écrite une fois et sert partout
-- (pages, API, questions guidées).
CREATE TABLE ref.indicateur (
  indicateur_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code          text NOT NULL UNIQUE CHECK (code ~ '^[A-Z][A-Z0-9_]+$'),
  libelle       text NOT NULL,
  definition    text NOT NULL,
  unite         text NOT NULL
                CHECK (unite IN ('personnes', 'pourcentage', 'pour_mille', 'ratio', 'annees')),
  nature        text NOT NULL CHECK (nature IN ('effectif', 'taux', 'flux', 'ratio')),
  source_id     smallint NOT NULL REFERENCES ref.source,
  -- Formule pour un indicateur dérivé (calculé en vue matérialisée), sinon NULL.
  formule       text,
  avertissement text,
  comparabilite text
);

-- Valeurs des dimensions autres que le sexe et l'âge (type d'activité, CSP...).
CREATE TABLE ref.modalite (
  modalite_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dimension   text NOT NULL CHECK (dimension ~ '^[a-z_]+$'),
  code        text NOT NULL,
  libelle     text NOT NULL,
  UNIQUE (dimension, code)
);
