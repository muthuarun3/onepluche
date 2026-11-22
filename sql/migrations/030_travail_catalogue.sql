-- Appli « Comment travaillent les Français ? », PR T1 : catalogue et séries de l'INSEE.
-- Dossier de conception de l'appli travail, étapes 3, 5 et 7. La rubrique et ses sept
-- thèmes s'ajoutent aux tables de la migration 026, sans toucher aux contraintes.
-- TAUX_CHOMAGE (trimestriel) reste dans la rubrique de l'appli 1 : /travail le relit.

INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire, avec_angles) VALUES
  ('TRAVAIL', 'Comment travaillent les Français ?', '/travail', 8, true, false);

INSERT INTO ref.theme (rubrique, code, libelle, ordre) VALUES
  ('TRAVAIL', 'CHERCHER_CREER', 'Qui cherche et qui crée', 1),
  ('TRAVAIL', 'EMPLOI', 'Qui travaille', 2),
  ('TRAVAIL', 'CONDITIONS', 'Comment', 3),
  ('TRAVAIL', 'SALAIRES', 'Combien ça paie', 4),
  ('TRAVAIL', 'TELETRAVAIL', 'Télétravail', 5),
  ('TRAVAIL', 'ACCIDENTS', 'Accidents du travail', 6),
  ('TRAVAIL', 'SYNDICATS_GREVES', 'Syndicats et grèves', 7);

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_EMPLOI', 'INSEE',
   'Estimations d''emploi : emploi salarié trimestriel et emploi total au 31 décembre',
   'https://api.insee.fr/series/BDM/dataflow/FR1/TCRED-EMPLOI-SALARIE-TRIM'),
  ('INSEE_SIDE', 'INSEE',
   'Créations d''entreprises (répertoire Sirene) et défaillances d''entreprises '
   '(Banque de France)',
   'https://api.insee.fr/series/BDM/dataflow/FR1/CREATIONS-ENTREPRISES-METHODE-2022');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('secteur', 'INTERIM', 'Intérim (compté dans le tertiaire marchand)'),
  ('statut_emploi', 'SALARIE', 'Salariés'),
  ('statut_emploi', 'NON_SALARIE', 'Indépendants (non-salariés)'),
  ('type_entreprise', 'MICRO', 'Micro-entrepreneurs');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme,
                            borne_min, borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'TRAVAIL', v.theme, v.borne_min, v.borne_max
FROM (VALUES
  ('INSEE_CHOM', 'TAUX_CHOMAGE_ANNUEL', 'Taux de chômage en moyenne annuelle',
   'Chômeurs au sens du BIT pour 100 actifs, en moyenne sur l''année, par sexe et par '
   'tranche d''âge (15-24 ans, 25-49 ans, 50 ans ou plus).',
   'pourcentage', 'taux', NULL,
   'Hors Mayotte. Métropole : taux localisés ; outre-mer et France : enquête Emploi. '
   'Les jeunes actifs sont peu nombreux : leur taux de chômage porte sur '
   'ceux qui travaillent ou cherchent, pas sur tous les jeunes (beaucoup étudient).',
   'Comparable entre territoires et dans le temps.', 'CHERCHER_CREER', 0, 80),
  ('INSEE_SIDE', 'CREATIONS_ENTREPRISES', 'Créations d''entreprises',
   'Entreprises créées dans le mois (immatriculations au répertoire Sirene), dont '
   'micro-entrepreneurs.',
   'nombre', 'flux', NULL,
   'Depuis 2009, les micro-entrepreneurs forment une grande part des créations ; beaucoup '
   'n''ont jamais de chiffre d''affaires. Données brutes : comparer un mois au même mois '
   'de l''année précédente.', NULL, 'CHERCHER_CREER', 0, NULL),
  ('INSEE_SIDE', 'DEFAILLANCES_ENTREPRISES', 'Défaillances d''entreprises',
   'Entreprises ayant fait l''objet, dans le trimestre, de l''ouverture d''une procédure '
   'de redressement ou de liquidation judiciaire (date du jugement).',
   'nombre', 'flux', NULL,
   'Une défaillance n''est pas toujours une fermeture : un redressement peut sauver '
   'l''entreprise. Hors Mayotte. Depuis 1995.', NULL, 'CHERCHER_CREER', 0, NULL),
  ('INSEE_EMPLOI', 'EMPLOI_SALARIE', 'Emploi salarié',
   'Salariés en fin de trimestre, par grand secteur d''activité, corrigé des variations '
   'saisonnières. L''intérim est donné à part et compris dans le tertiaire marchand.',
   'personnes', 'effectif', NULL,
   'Les intérimaires sont comptés dans le département de leur agence, pas forcément là '
   'où ils travaillent. Hors Mayotte. Depuis 2011. Les derniers trimestres sont '
   'provisoires.',
   NULL, 'EMPLOI', 0, NULL),
  ('INSEE_EMPLOI', 'PART_INTERIM', 'Part de l''intérim dans l''emploi salarié',
   'Intérimaires pour 100 salariés, en fin de trimestre.',
   'pourcentage', 'taux', '100 × intérimaires / salariés',
   'Les intérimaires sont comptés dans le département de leur agence. Hors Mayotte.',
   NULL, 'EMPLOI', 0, 15),
  ('INSEE_EMPLOI', 'EMPLOI_TOTAL', 'Emploi total',
   'Personnes en emploi au 31 décembre, salariées ou indépendantes (non-salariées), '
   'comptées sur leur lieu de travail.',
   'personnes', 'effectif', NULL,
   'Base 2018 : séries arrêtées en 2024 par l''INSEE, en attente de la base suivante.',
   NULL, 'EMPLOI', 0, NULL),
  ('INSEE_EMPLOI', 'PART_INDEPENDANTS', 'Part des indépendants dans l''emploi',
   'Indépendants (non-salariés : artisans, commerçants, professions libérales, '
   'agriculteurs, micro-entrepreneurs) pour 100 emplois, au 31 décembre.',
   'pourcentage', 'taux', '100 × indépendants / emplois',
   'Base 2018 : séries arrêtées en 2024 par l''INSEE.', NULL, 'EMPLOI', 0, 60)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement,
        comparabilite, theme, borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;
