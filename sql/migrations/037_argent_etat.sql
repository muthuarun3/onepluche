-- Appli « Où va l'argent public ? », PR B : budget de l'État. Dossier de conception de
-- l'appli, étapes 5 et 6. Solde, dépenses et recettes du budget général cumulés mois par
-- mois (situation mensuelle budgétaire), crédits votés et consommés par mission (PLRG).

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('SITUATION_MENSUELLE_ETAT', 'Ministère de l''Économie',
   'Situation mensuelle budgétaire de l''État',
   'https://data.economie.gouv.fr/explore/dataset/situations-mensuelles-budgetaires-series-longues/'),
  ('PLRG_ETAT', 'Ministère de l''Économie',
   'Projet de loi relatif aux résultats de la gestion (PLRG) : crédits par mission',
   'https://data.economie.gouv.fr/explore/?q=plrg');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('impot_etat', 'TVA', 'TVA'),
  ('impot_etat', 'IR', 'Impôt sur le revenu'),
  ('impot_etat', 'IS', 'Impôt sur les sociétés'),
  ('impot_etat', 'TICPE', 'Taxe sur les carburants et combustibles (TICPE)'),
  ('impot_etat', 'AUTRES', 'Autres impôts');

-- Les missions du budget général de 2023 à 2025 ; « Travail et emploi » a changé de nom
-- en 2025 et garde son code. Une mission nouvelle fait rejeter l'import (docs/TASKS.md).
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('mission_etat', 'ACTION_EXTERIEURE_DE_L_ETAT', 'Action extérieure de l''État'),
  ('mission_etat', 'ADMINISTRATION_GENERALE_ET_TERRITORIALE_DE_L_ETAT', 'Administration générale et territoriale de l''État'),
  ('mission_etat', 'AGRICULTURE_ALIMENTATION_FORET_ET_AFFAIRES_RURALES', 'Agriculture, alimentation, forêt et affaires rurales'),
  ('mission_etat', 'AIDE_PUBLIQUE_AU_DEVELOPPEMENT', 'Aide publique au développement'),
  ('mission_etat', 'ANCIENS_COMBATTANTS_MEMOIRE_ET_LIENS_AVEC_LA_NATION', 'Anciens combattants, mémoire et liens avec la Nation'),
  ('mission_etat', 'COHESION_DES_TERRITOIRES', 'Cohésion des territoires'),
  ('mission_etat', 'CONSEIL_ET_CONTROLE_DE_L_ETAT', 'Conseil et contrôle de l''État'),
  ('mission_etat', 'CREDITS_NON_REPARTIS', 'Crédits non répartis'),
  ('mission_etat', 'CULTURE', 'Culture'),
  ('mission_etat', 'DEFENSE', 'Défense'),
  ('mission_etat', 'DIRECTION_DE_L_ACTION_DU_GOUVERNEMENT', 'Direction de l''action du Gouvernement'),
  ('mission_etat', 'ECOLOGIE_DEVELOPPEMENT_ET_MOBILITE_DURABLES', 'Écologie, développement et mobilité durables'),
  ('mission_etat', 'ECONOMIE', 'Économie'),
  ('mission_etat', 'ENGAGEMENTS_FINANCIERS_DE_L_ETAT', 'Engagements financiers de l''État'),
  ('mission_etat', 'ENSEIGNEMENT_SCOLAIRE', 'Enseignement scolaire'),
  ('mission_etat', 'GESTION_DES_FINANCES_PUBLIQUES', 'Gestion des finances publiques'),
  ('mission_etat', 'IMMIGRATION_ASILE_ET_INTEGRATION', 'Immigration, asile et intégration'),
  ('mission_etat', 'INVESTIR_POUR_LA_FRANCE_DE_2030', 'Investir pour la France de 2030'),
  ('mission_etat', 'JUSTICE', 'Justice'),
  ('mission_etat', 'MEDIAS_LIVRE_ET_INDUSTRIES_CULTURELLES', 'Médias, livre et industries culturelles'),
  ('mission_etat', 'OUTRE_MER', 'Outre-Mer'),
  ('mission_etat', 'PLAN_DE_RELANCE', 'Plan de relance'),
  ('mission_etat', 'POUVOIRS_PUBLICS', 'Pouvoirs publics'),
  ('mission_etat', 'RECHERCHE_ET_ENSEIGNEMENT_SUPERIEUR', 'Recherche et enseignement supérieur'),
  ('mission_etat', 'REGIMES_SOCIAUX_ET_DE_RETRAITE', 'Régimes sociaux et de retraite'),
  ('mission_etat', 'RELATIONS_AVEC_LES_COLLECTIVITES_TERRITORIALES', 'Relations avec les collectivités territoriales'),
  ('mission_etat', 'REMBOURSEMENTS_ET_DEGREVEMENTS', 'Remboursements et dégrèvements'),
  ('mission_etat', 'SANTE', 'Santé'),
  ('mission_etat', 'SECURITES', 'Sécurités'),
  ('mission_etat', 'SOLIDARITE_INSERTION_ET_EGALITE_DES_CHANCES', 'Solidarité, insertion et égalité des chances'),
  ('mission_etat', 'SPORT_JEUNESSE_ET_VIE_ASSOCIATIVE', 'Sport, jeunesse et vie associative'),
  ('mission_etat', 'TRANSFORMATION_ET_FONCTION_PUBLIQUES', 'Transformation et fonction publiques'),
  ('mission_etat', 'TRAVAIL_EMPLOI', 'Travail, emploi et administration des ministères sociaux');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, borne_min,
                            borne_max)
SELECT v.code, v.libelle, v.definition, 'milliards_euros', 'flux', s.source_id, NULL,
       v.avertissement, v.comparabilite, 'ARGENT', 'ETAT', v.borne_min, v.borne_max
FROM (VALUES
  ('SITUATION_MENSUELLE_ETAT', 'SOLDE_ETAT', 'Solde budgétaire de l''État, cumulé depuis janvier',
   'Recettes moins dépenses du budget de l''État (budget général, comptes spéciaux et budgets '
   'annexes), cumulées du 1er janvier à la fin du mois. Un solde négatif est un déficit.',
   'Comptabilité budgétaire de l''État (encaissements et décaissements) : ce n''est pas le '
   'déficit public au sens de Maastricht, qui couvre aussi la Sécurité sociale et les '
   'collectivités.',
   'Mois par mois depuis janvier 2024 ; le cumul repart de zéro chaque 1er janvier.',
   -1000, 1000),
  ('SITUATION_MENSUELLE_ETAT', 'DEPENSES_ETAT', 'Dépenses nettes du budget général, cumulées',
   'Dépenses du budget général de l''État, nettes des remboursements et dégrèvements '
   'd''impôts, cumulées du 1er janvier à la fin du mois.',
   NULL, 'Mois par mois depuis janvier 2024.', 0, 2000),
  ('SITUATION_MENSUELLE_ETAT', 'RECETTES_ETAT', 'Recettes nettes du budget général, cumulées',
   'Recettes fiscales et non fiscales du budget général, nettes des remboursements et '
   'dégrèvements, cumulées du 1er janvier à la fin du mois.',
   NULL, 'Mois par mois depuis janvier 2024.', 0, 2000),
  ('SITUATION_MENSUELLE_ETAT', 'RECETTES_FISCALES_ETAT', 'Recettes fiscales nettes de l''État',
   'Impôts perçus par l''État, nets des remboursements et dégrèvements, cumulés du 1er '
   'janvier à la fin du mois, par impôt.',
   'Une partie de la TVA et de la TICPE est reversée à la Sécurité sociale et aux '
   'collectivités : seule la part de l''État est comptée ici.',
   'Mois par mois depuis janvier 2024.', -100, 2000),
  ('PLRG_ETAT', 'CREDITS_VOTES', 'Crédits votés par mission',
   'Crédits de paiement ouverts par la loi de finances initiale de l''année, par mission du '
   'budget général.',
   'Avant les lois de finances rectificatives, reports et annulations en cours d''année.',
   'Missions du budget général de 2023 à 2025.', 0, 2000),
  ('PLRG_ETAT', 'CREDITS_CONSOMMES', 'Crédits consommés par mission',
   'Dépenses constatées en fin d''année, par mission du budget général (crédits de '
   'paiement).',
   '« Remboursements et dégrèvements » rend aux contribuables des impôts trop perçus : ce '
   'n''est pas une politique publique.',
   'Missions du budget général de 2023 à 2025 ; l''année écoulée paraît en avril.', 0, 2000)
) AS v (source, code, libelle, definition, avertissement, comparabilite, borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;

-- Répartition par modalité d'un indicateur mensuel, à une date (recettes fiscales de
-- l'État par impôt en décembre) : api.repartition ne porte que l'année.
CREATE VIEW api.repartition_mensuelle AS
SELECT i.code AS indicateur,
       m.dimension,
       m.code AS modalite,
       m.libelle,
       m.modalite_id AS ordre,
       t.niveau,
       t.code,
       o.periode,
       o.valeur,
       o.statut = 'PROVISOIRE' AS provisoire
FROM stat.observation o
JOIN ref.modalite m USING (modalite_id)
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
WHERE o.periode_type = 'MOIS' AND o.sexe = 'T'
  AND o.age_min IS NULL AND o.age_max IS NULL;

GRANT SELECT ON api.repartition_mensuelle TO demo_lecture;
