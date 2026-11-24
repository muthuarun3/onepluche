-- Appli « Où va l'argent public ? », PR C : collectivités locales. Dossier de conception
-- de l'appli, étapes 5 et 6. Dépenses et dette du département (ou de la collectivité
-- unique), des communes et des intercommunalités, par département, depuis 2016.

INSERT INTO ref.unite (code) VALUES ('millions_euros') ON CONFLICT DO NOTHING;

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('DGFIP_COMPTES_LOCAUX', 'DGFiP',
   'Comptes individuels des collectivités locales (départements, communes, groupements à fiscalité propre)',
   'https://data.economie.gouv.fr/explore/?q=comptes+individuels');

-- Postes de dépense des comptes individuels (départements et communes).
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('poste_local', 'PERSONNEL', 'Personnel'),
  ('poste_local', 'AIDES_SOCIALES', 'Aides sociales versées (RSA, autonomie, handicap)'),
  ('poste_local', 'HEBERGEMENT', 'Hébergement (enfance, personnes âgées, handicapées)'),
  ('poste_local', 'ACHATS', 'Achats et charges externes'),
  ('poste_local', 'AUTRES_FONCTIONNEMENT', 'Autres dépenses de fonctionnement'),
  ('poste_local', 'EQUIPEMENT', 'Équipement (travaux, routes, bâtiments…)'),
  ('poste_local', 'AUTRES_INVESTISSEMENT', 'Autres investissements (subventions d''équipement…)');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, borne_min,
                            borne_max)
SELECT v.code, v.libelle, v.definition, 'millions_euros', v.nature, s.source_id, v.formule,
       v.avertissement,
       'Comptes de gestion de chaque collectivité, en euros de chaque année, depuis 2016.',
       'ARGENT', 'LOCAL', 0, v.borne_max
FROM (VALUES
  ('DEPENSES_DEPARTEMENT', 'Dépenses du département',
   'Dépenses de fonctionnement et d''investissement du conseil départemental (ou de la '
   'collectivité unique), hors remboursement du capital des emprunts.',
   'flux', 'charges de fonctionnement + emplois d''investissement − remboursement d''emprunts',
   'Alsace (depuis 2021), Corse (depuis 2018), Martinique, Guyane : une collectivité unique, '
   'aussi chargée des compétences de la région pour les trois dernières. Paris : le budget '
   'départemental est dans celui de la Ville, compté avec les communes.',
   200000),
  ('DETTE_DEPARTEMENT', 'Dette du département',
   'Encours de la dette du conseil départemental (ou de la collectivité unique) au 31 '
   'décembre.', 'effectif', NULL, NULL, 200000),
  ('DEPENSES_COMMUNES', 'Dépenses des communes',
   'Dépenses de fonctionnement et d''investissement de toutes les communes du département '
   '(budgets principaux), hors remboursement du capital des emprunts.',
   'flux', 'charges de fonctionnement + dépenses d''investissement − remboursement d''emprunts',
   'Budgets principaux seulement : les budgets annexes (eau, transports…) n''y sont pas.',
   200000),
  ('DETTE_COMMUNES', 'Dette des communes',
   'Encours de la dette des communes du département au 31 décembre.', 'effectif', NULL,
   NULL, 200000),
  ('DEPENSES_INTERCO', 'Dépenses des intercommunalités',
   'Dépenses de fonctionnement et d''investissement des groupements de communes à '
   'fiscalité propre (communautés, métropoles) dont le siège est dans le département, hors '
   'remboursement du capital des emprunts.',
   'flux', 'charges de fonctionnement + emplois d''investissement − remboursement d''emprunts',
   'Un groupement est compté dans le département de son siège, même s''il en déborde. La '
   'Métropole de Lyon, qui exerce aussi les compétences du département sur son territoire, '
   'est comptée ici.',
   200000),
  ('DETTE_INTERCO', 'Dette des intercommunalités',
   'Encours de la dette des groupements à fiscalité propre dont le siège est dans le '
   'département, au 31 décembre.', 'effectif', NULL, NULL, 200000)
) AS v (code, libelle, definition, nature, formule, avertissement, borne_max)
CROSS JOIN ref.source s
WHERE s.code = 'DGFIP_COMPTES_LOCAUX';
