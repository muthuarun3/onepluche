-- Appli 3 « Que pensent et votent les Français ? » (rubrique /votes), PR V1 : fondations.
-- Dossier de conception de l'appli 3, étapes 3 et 5 (validées le 22/11/2026).
--
-- Aucun indicateur ici : la rubrique, ses thèmes et sources, deux territoires hors
-- département, le type de période SCRUTIN, les 20 tours retenus et la table qui relie
-- chaque choix (candidat, liste ou nuance) à son scrutin. Les indicateurs arrivent avec
-- les connecteurs (PR V2 résultats, V3 élus).

-- Rubrique et thèmes (tables créées par la migration 026). Ordre 4 réservé à cette appli.
INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire, avec_angles) VALUES
  ('VOTES', 'Que pensent et votent les Français ?', '/votes', 4, true, false);

INSERT INTO ref.theme (rubrique, code, libelle, ordre) VALUES
  ('VOTES', 'PARTICIPATION', 'Qui vote ?', 1),
  ('VOTES', 'RESULTATS', 'Pour qui ?', 2),
  ('VOTES', 'ELUS', 'Qui sont les élus ?', 3);

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('MI_ELECTIONS', 'Ministère de l''Intérieur (données agrégées par data.gouv.fr)',
   'Résultats des élections par bureau de vote, depuis 1999',
   'https://www.data.gouv.fr/fr/datasets/donnees-des-elections-agregees/'),
  ('MI_RNE', 'Ministère de l''Intérieur', 'Répertoire national des élus',
   'https://www.data.gouv.fr/fr/datasets/repertoire-national-des-elus-1/');

-- Électeurs qui ne sont dans aucun des 101 départements. Le total France des élections
-- les comprend : France = départements + territoires HORS_DEP. Les autres rubriques ne
-- lisent que FRANCE, REG et DEP.
ALTER TABLE ref.territoire DROP CONSTRAINT territoire_niveau_check;
ALTER TABLE ref.territoire ADD CONSTRAINT territoire_niveau_check
  CHECK (niveau IN ('FRANCE', 'REG', 'DEP', 'HORS_DEP'));

INSERT INTO ref.territoire (niveau, code, libelle, parent_id, cog_millesime)
SELECT 'HORS_DEP', v.code, v.libelle, f.territoire_id, 2026
FROM (VALUES ('ZZ', 'Français de l''étranger'),
             ('COM', 'Collectivités d''outre-mer')) AS v (code, libelle)
CROSS JOIN ref.territoire f
WHERE f.niveau = 'FRANCE' AND f.code = 'FR';

COMMENT ON COLUMN ref.territoire.niveau IS
  'FRANCE, REG, DEP ; HORS_DEP = électeurs hors département (rubrique VOTES seulement) : '
  'ZZ Français de l''étranger, COM Saint-Pierre-et-Miquelon, Saint-Barthélemy, '
  'Saint-Martin, Wallis-et-Futuna, Polynésie française, Nouvelle-Calédonie.';

-- Une observation de scrutin est datée du jour du tour.
ALTER TABLE stat.observation DROP CONSTRAINT observation_periode_type_check;
ALTER TABLE stat.observation ADD CONSTRAINT observation_periode_type_check
  CHECK (periode_type IN ('1ER_JANVIER', 'ANNEE', 'TRIMESTRE', 'RP', 'MOIS', 'SCRUTIN'));

-- Un scrutin = un tour d'une élection, modalité de la dimension « scrutin ».
CREATE TABLE ref.scrutin (
  modalite_id smallint PRIMARY KEY REFERENCES ref.modalite,
  election    text     NOT NULL
              CHECK (election IN ('PRESIDENTIELLE', 'LEGISLATIVES', 'EUROPEENNES', 'MUNICIPALES')),
  annee       smallint NOT NULL CHECK (annee BETWEEN 1999 AND 2100),
  tour        smallint NOT NULL CHECK (tour IN (1, 2)),
  jour        date     NOT NULL UNIQUE CHECK (extract(year FROM jour) = annee),
  -- Ce que l'électeur choisit, tel que publié : candidat, liste, ou nuance quand les
  -- candidats changent d'une circonscription à l'autre. NULL : participation seulement.
  type_choix  text     CHECK (type_choix IN ('CANDIDAT', 'LISTE', 'NUANCE')),
  UNIQUE (election, annee, tour)
);

COMMENT ON TABLE ref.scrutin IS
  'Tours d''élection retenus (dossier de l''appli 3, étape 1). Avant 2014, les votes '
  'blancs étaient comptés avec les nuls.';

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('scrutin', 'PRES_2002_T1', 'Présidentielle 2002, 1er tour'),
  ('scrutin', 'PRES_2002_T2', 'Présidentielle 2002, 2nd tour'),
  ('scrutin', 'PRES_2007_T1', 'Présidentielle 2007, 1er tour'),
  ('scrutin', 'PRES_2007_T2', 'Présidentielle 2007, 2nd tour'),
  ('scrutin', 'PRES_2012_T1', 'Présidentielle 2012, 1er tour'),
  ('scrutin', 'PRES_2012_T2', 'Présidentielle 2012, 2nd tour'),
  ('scrutin', 'PRES_2017_T1', 'Présidentielle 2017, 1er tour'),
  ('scrutin', 'PRES_2017_T2', 'Présidentielle 2017, 2nd tour'),
  ('scrutin', 'EURO_2019_T1', 'Européennes 2019'),
  ('scrutin', 'MUNI_2020_T1', 'Municipales 2020, 1er tour'),
  ('scrutin', 'MUNI_2020_T2', 'Municipales 2020, 2nd tour'),
  ('scrutin', 'PRES_2022_T1', 'Présidentielle 2022, 1er tour'),
  ('scrutin', 'PRES_2022_T2', 'Présidentielle 2022, 2nd tour'),
  ('scrutin', 'LEGI_2022_T1', 'Législatives 2022, 1er tour'),
  ('scrutin', 'LEGI_2022_T2', 'Législatives 2022, 2nd tour'),
  ('scrutin', 'EURO_2024_T1', 'Européennes 2024'),
  ('scrutin', 'LEGI_2024_T1', 'Législatives 2024, 1er tour'),
  ('scrutin', 'LEGI_2024_T2', 'Législatives 2024, 2nd tour'),
  ('scrutin', 'MUNI_2026_T1', 'Municipales 2026, 1er tour'),
  ('scrutin', 'MUNI_2026_T2', 'Municipales 2026, 2nd tour');

INSERT INTO ref.scrutin (modalite_id, election, annee, tour, jour, type_choix)
SELECT m.modalite_id, v.election, v.annee, v.tour, v.jour::date, v.type_choix
FROM (VALUES
  ('PRES_2002_T1', 'PRESIDENTIELLE', 2002, 1, '2002-04-21', 'CANDIDAT'),
  ('PRES_2002_T2', 'PRESIDENTIELLE', 2002, 2, '2002-05-05', 'CANDIDAT'),
  ('PRES_2007_T1', 'PRESIDENTIELLE', 2007, 1, '2007-04-22', 'CANDIDAT'),
  ('PRES_2007_T2', 'PRESIDENTIELLE', 2007, 2, '2007-05-06', 'CANDIDAT'),
  ('PRES_2012_T1', 'PRESIDENTIELLE', 2012, 1, '2012-04-22', 'CANDIDAT'),
  ('PRES_2012_T2', 'PRESIDENTIELLE', 2012, 2, '2012-05-06', 'CANDIDAT'),
  ('PRES_2017_T1', 'PRESIDENTIELLE', 2017, 1, '2017-04-23', 'CANDIDAT'),
  ('PRES_2017_T2', 'PRESIDENTIELLE', 2017, 2, '2017-05-07', 'CANDIDAT'),
  ('EURO_2019_T1', 'EUROPEENNES', 2019, 1, '2019-05-26', 'LISTE'),
  ('MUNI_2020_T1', 'MUNICIPALES', 2020, 1, '2020-03-15', NULL),
  ('MUNI_2020_T2', 'MUNICIPALES', 2020, 2, '2020-06-28', NULL),
  ('PRES_2022_T1', 'PRESIDENTIELLE', 2022, 1, '2022-04-10', 'CANDIDAT'),
  ('PRES_2022_T2', 'PRESIDENTIELLE', 2022, 2, '2022-04-24', 'CANDIDAT'),
  ('LEGI_2022_T1', 'LEGISLATIVES', 2022, 1, '2022-06-12', 'NUANCE'),
  ('LEGI_2022_T2', 'LEGISLATIVES', 2022, 2, '2022-06-19', 'NUANCE'),
  ('EURO_2024_T1', 'EUROPEENNES', 2024, 1, '2024-06-09', 'LISTE'),
  ('LEGI_2024_T1', 'LEGISLATIVES', 2024, 1, '2024-06-30', 'NUANCE'),
  ('LEGI_2024_T2', 'LEGISLATIVES', 2024, 2, '2024-07-07', 'NUANCE'),
  ('MUNI_2026_T1', 'MUNICIPALES', 2026, 1, '2026-03-15', NULL),
  ('MUNI_2026_T2', 'MUNICIPALES', 2026, 2, '2026-03-22', NULL)
) AS v (code, election, annee, tour, jour, type_choix)
JOIN ref.modalite m ON m.dimension = 'scrutin' AND m.code = v.code;

-- Un choix = ce que l'électeur a pu choisir à un scrutin, modalité de la dimension
-- « choix ». Libellés officiels tels quels ; pas de regroupement en blocs.
CREATE TABLE ref.choix_scrutin (
  modalite_id     smallint PRIMARY KEY REFERENCES ref.modalite,
  scrutin_id      smallint NOT NULL REFERENCES ref.scrutin,
  -- Numéro de panneau (candidat, liste) ; NULL pour une nuance.
  panneau         smallint CHECK (panneau > 0),
  -- Nuance attribuée par le ministère (législatives, européennes) et sa définition.
  nuance          text     CHECK (nuance ~ '^[A-Z]{2,5}$'),
  nuance_libelle  text,
  -- Sexe du candidat ou de la tête de liste ; NULL pour une nuance.
  sexe            char(1)  CHECK (sexe IN ('F', 'H')),
  CHECK (panneau IS NOT NULL OR nuance IS NOT NULL)
);
CREATE INDEX ON ref.choix_scrutin (scrutin_id);

-- Le rôle d'import ne lit que les référentiels. Il ajoute un choix par cette seule
-- fonction, qui n'écrit que dans la dimension « choix » d'un scrutin connu.
CREATE FUNCTION ref.ajouter_choix(
  p_scrutin text, p_code text, p_libelle text, p_panneau smallint, p_nuance text,
  p_nuance_libelle text, p_sexe char(1)
) RETURNS smallint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ref AS $$
DECLARE
  v_scrutin  smallint;
  v_modalite smallint;
BEGIN
  SELECT s.modalite_id INTO v_scrutin
  FROM ref.scrutin s JOIN ref.modalite m USING (modalite_id)
  WHERE m.code = p_scrutin;
  IF v_scrutin IS NULL THEN
    RAISE EXCEPTION 'Scrutin inconnu : %', p_scrutin USING ERRCODE = 'foreign_key_violation';
  END IF;
  IF p_code !~ ('^' || p_scrutin || '_[A-Z0-9]+$') THEN
    RAISE EXCEPTION 'Le code du choix % doit commencer par %_', p_code, p_scrutin
      USING ERRCODE = 'check_violation';
  END IF;

  INSERT INTO ref.modalite (dimension, code, libelle) VALUES ('choix', p_code, p_libelle)
  ON CONFLICT (dimension, code) DO UPDATE SET libelle = EXCLUDED.libelle
  RETURNING modalite_id INTO v_modalite;

  INSERT INTO ref.choix_scrutin AS c
    (modalite_id, scrutin_id, panneau, nuance, nuance_libelle, sexe)
  VALUES (v_modalite, v_scrutin, p_panneau, p_nuance, p_nuance_libelle, p_sexe)
  ON CONFLICT (modalite_id) DO UPDATE
    SET panneau = EXCLUDED.panneau, nuance = EXCLUDED.nuance,
        nuance_libelle = EXCLUDED.nuance_libelle, sexe = EXCLUDED.sexe
  WHERE c.scrutin_id = EXCLUDED.scrutin_id;
  RETURN v_modalite;
END;
$$;

REVOKE ALL ON FUNCTION ref.ajouter_choix(text, text, text, smallint, text, text, char)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ref.ajouter_choix(text, text, text, smallint, text, text, char)
  TO demo_import;
GRANT SELECT ON ref.scrutin, ref.choix_scrutin TO demo_import;

-- Mandats des élus (Répertoire national des élus), modalités de la dimension « mandat ».
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('mandat', 'MAIRE', 'Maires'),
  ('mandat', 'CONSEILLER_DEP', 'Conseillers départementaux'),
  ('mandat', 'DEPUTE', 'Députés'),
  ('mandat', 'SENATEUR', 'Sénateurs');

-- Vues lues par l'application.
CREATE VIEW api.scrutin AS
SELECT m.code, m.libelle, s.election, s.annee, s.tour, s.jour, s.type_choix
FROM ref.scrutin s
JOIN ref.modalite m USING (modalite_id);

CREATE VIEW api.choix_scrutin AS
SELECT ms.code AS scrutin, mc.code, mc.libelle, c.panneau, c.nuance, c.nuance_libelle, c.sexe
FROM ref.choix_scrutin c
JOIN ref.modalite mc ON mc.modalite_id = c.modalite_id
JOIN ref.modalite ms ON ms.modalite_id = c.scrutin_id;

GRANT SELECT ON api.scrutin, api.choix_scrutin TO demo_lecture;
