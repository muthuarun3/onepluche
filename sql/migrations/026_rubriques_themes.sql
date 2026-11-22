-- Rubriques, thèmes et unités en tables de référence, au lieu de contraintes CHECK.
-- Six applications se construisent en parallèle (une question = une rubrique) : chacune
-- réécrivait ces contraintes, et les PR se marchaient dessus. Désormais, une nouvelle
-- rubrique ajoute simplement ses lignes dans ref.rubrique, ref.theme et ref.unite.
-- Dossier de conception de l'appli 3, étape 3. Aucune donnée ne change.

-- Une rubrique = une application de l'accueil.
CREATE TABLE ref.rubrique (
  code      text PRIMARY KEY CHECK (code ~ '^[A-Z][A-Z0-9_]+$'),
  libelle   text NOT NULL,
  chemin    text NOT NULL UNIQUE CHECK (chemin ~ '^/[a-z0-9-]+$'),
  ordre     smallint NOT NULL UNIQUE,
  -- Chaque indicateur de la rubrique appartient à un thème.
  theme_obligatoire boolean NOT NULL DEFAULT false,
  -- Angles de lecture (accès, coût, manque) admis pour ses indicateurs.
  avec_angles boolean NOT NULL DEFAULT false
);

INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire, avec_angles) VALUES
  ('QUI', 'Qui sont les Français ?', '/francais', 1, false, false),
  ('BESOINS', 'De quoi les Français ont besoin ?', '/besoins', 2, true, true);

-- Un thème appartient à une rubrique ; deux rubriques peuvent réutiliser le même code.
CREATE TABLE ref.theme (
  rubrique text NOT NULL REFERENCES ref.rubrique,
  code     text NOT NULL CHECK (code ~ '^[A-Z][A-Z0-9_]+$'),
  libelle  text NOT NULL,
  ordre    smallint NOT NULL,
  PRIMARY KEY (rubrique, code),
  UNIQUE (rubrique, ordre)
);

INSERT INTO ref.theme (rubrique, code, libelle, ordre) VALUES
  ('BESOINS', 'BUDGET', 'Budget des ménages', 1),
  ('BESOINS', 'LOGEMENT', 'Logement', 2),
  ('BESOINS', 'ENERGIE', 'Énergie', 3),
  ('BESOINS', 'EAU', 'Eau', 4),
  ('BESOINS', 'ALIMENTATION', 'Alimentation', 5),
  ('BESOINS', 'TRANSPORTS', 'Transports', 6),
  ('BESOINS', 'SOINS', 'Accès aux soins', 7),
  ('BESOINS', 'NUMERIQUE', 'Numérique', 8),
  ('BESOINS', 'GARDE', 'Garde d''enfants', 9);

CREATE TABLE ref.unite (
  code text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]+$')
);

INSERT INTO ref.unite (code) VALUES
  ('personnes'), ('pourcentage'), ('pour_mille'), ('ratio'), ('annees'), ('logements'),
  ('nombre'), ('euros'), ('euros_m2'), ('mwh'), ('indice'), ('consultations_hab'),
  ('pour_10000'), ('millions_euros'), ('euros_litre');

-- Les anciennes contraintes CHECK laissent la place à des clés étrangères.
ALTER TABLE ref.indicateur
  DROP CONSTRAINT indicateur_rubrique_check,
  DROP CONSTRAINT indicateur_theme_check,
  DROP CONSTRAINT indicateur_angle_check,
  DROP CONSTRAINT indicateur_unite_check,
  DROP CONSTRAINT indicateur_besoins_theme_check,
  DROP CONSTRAINT indicateur_besoins_angle_check,
  ADD CONSTRAINT indicateur_rubrique_fkey FOREIGN KEY (rubrique) REFERENCES ref.rubrique,
  -- Thème NULL admis par la clé (MATCH SIMPLE) ; l'obligation est vérifiée plus bas.
  ADD CONSTRAINT indicateur_theme_fkey
    FOREIGN KEY (rubrique, theme) REFERENCES ref.theme (rubrique, code),
  ADD CONSTRAINT indicateur_unite_fkey FOREIGN KEY (unite) REFERENCES ref.unite,
  ADD CONSTRAINT indicateur_angle_check CHECK (angle IN ('ACCES', 'COUT', 'MANQUE'));

-- Thème obligatoire et angles admis : règles portées par la rubrique. Une contrainte CHECK
-- ne peut pas lire une autre table, d'où ce déclencheur (même code d'erreur qu'un CHECK).
CREATE FUNCTION ref.verifier_indicateur_rubrique() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  r ref.rubrique;
BEGIN
  SELECT * INTO r FROM ref.rubrique WHERE code = NEW.rubrique;
  IF r.theme_obligatoire AND NEW.theme IS NULL THEN
    RAISE EXCEPTION 'L''indicateur % de la rubrique % doit avoir un thème',
      NEW.code, NEW.rubrique USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.angle IS NOT NULL AND NOT r.avec_angles THEN
    RAISE EXCEPTION 'La rubrique % n''admet pas d''angle de lecture (indicateur %)',
      NEW.rubrique, NEW.code USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER indicateur_rubrique
  BEFORE INSERT OR UPDATE OF rubrique, theme, angle ON ref.indicateur
  FOR EACH ROW EXECUTE FUNCTION ref.verifier_indicateur_rubrique();

GRANT SELECT ON ref.rubrique, ref.theme, ref.unite TO demo_import;

-- Rubriques et thèmes lisibles par l'application (barre latérale, filtres de l'API).
CREATE VIEW api.theme AS
SELECT r.code    AS rubrique,
       r.libelle AS rubrique_libelle,
       r.chemin  AS rubrique_chemin,
       r.ordre   AS rubrique_ordre,
       t.code    AS theme,
       t.libelle AS theme_libelle,
       t.ordre   AS theme_ordre
FROM ref.rubrique r
LEFT JOIN ref.theme t ON t.rubrique = r.code;

GRANT SELECT ON api.theme TO demo_lecture;
