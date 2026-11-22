-- Appli « Où va l'argent public ? », PR A : vue France. Dossier de conception de l'appli,
-- étapes 5 et 6. Dépenses par fonction et par étage (État, Sécurité sociale, collectivités),
-- recettes par nature, prélèvements obligatoires, solde et dette publics.
--
-- Source : les tableaux des comptes nationaux annuels (INSEE, base 2020, « Les comptes de
-- la Nation »). Le jeu Melodi DD_CNA_APU prévu au dossier n'est pas utilisable en l'état :
-- ses totaux ne sont pas consolidés entre administrations (2 203 Md€ de dépenses en 2024,
-- contre 1 672 Md€ publiés) et la ventilation par fonction y manque.

INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire, avec_angles) VALUES
  ('ARGENT', 'Où va l''argent public ?', '/argent-public', 5, true, false);

INSERT INTO ref.theme (rubrique, code, libelle, ordre) VALUES
  ('ARGENT', 'DEPENSES', 'Dépenses publiques', 1),
  ('ARGENT', 'RECETTES', 'Recettes publiques', 2),
  ('ARGENT', 'DETTE', 'Déficit et dette', 3),
  ('ARGENT', 'ETAT', 'Budget de l''État', 4),
  ('ARGENT', 'LOCAL', 'Collectivités locales', 5),
  ('ARGENT', 'MENAGE', 'Impôts d''un ménage type', 6),
  ('ARGENT', 'CLIMAT', 'Catastrophes naturelles', 7);

INSERT INTO ref.unite (code) VALUES ('milliards_euros');

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_COMPTES_APU', 'INSEE',
   'Comptes nationaux annuels (base 2020) : comptes des administrations publiques',
   'https://www.insee.fr/fr/statistiques/2381404'),
  ('INSEE_DETTE_TRIM', 'INSEE',
   'Dette trimestrielle des administrations publiques au sens de Maastricht (base 2020)',
   'https://www.insee.fr/fr/statistiques/serie/010777616');

-- Les dix grandes fonctions de la nomenclature internationale COFOG (CFAP en français).
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('fonction_apu', 'PROTECTION_SOCIALE', 'Protection sociale (retraites, famille, chômage…)'),
  ('fonction_apu', 'SANTE', 'Santé'),
  ('fonction_apu', 'SERVICES_GENERAUX', 'Services généraux (dont intérêts de la dette)'),
  ('fonction_apu', 'AFFAIRES_ECONOMIQUES', 'Affaires économiques (transports, énergie, emploi…)'),
  ('fonction_apu', 'ENSEIGNEMENT', 'Enseignement'),
  ('fonction_apu', 'DEFENSE', 'Défense'),
  ('fonction_apu', 'ORDRE_SECURITE', 'Ordre et sécurité publics'),
  ('fonction_apu', 'LOISIRS_CULTURE', 'Loisirs, culture et culte'),
  ('fonction_apu', 'LOGEMENT_EQUIPEMENTS', 'Logement et équipements collectifs'),
  ('fonction_apu', 'ENVIRONNEMENT', 'Protection de l''environnement'),
  ('etage_apu', 'CENTRALE', 'État et organismes nationaux'),
  ('etage_apu', 'SECU', 'Sécurité sociale'),
  ('etage_apu', 'LOCALE', 'Collectivités locales'),
  ('nature_recette', 'COTISATIONS', 'Cotisations sociales'),
  ('nature_recette', 'PRODUCTION', 'TVA et autres impôts sur la production'),
  ('nature_recette', 'REVENU_PATRIMOINE', 'Impôts sur le revenu et le patrimoine (dont CSG)'),
  ('nature_recette', 'AUTRES', 'Autres recettes (ventes, revenus de la propriété…)');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, borne_min,
                            borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement,
       'Comptabilité nationale (base 2020) : série comparable dans le temps, en euros de '
       'chaque année.',
       'ARGENT', v.theme, v.borne_min, v.borne_max
FROM (VALUES
  ('INSEE_COMPTES_APU', 'DEPENSES_APU', 'Dépense publique',
   'Dépenses de l''ensemble des administrations publiques (État, organismes nationaux, '
   'collectivités locales, Sécurité sociale), consolidées : un versement d''une '
   'administration à une autre n''est compté qu''une fois.',
   'milliards_euros', 'flux', NULL,
   'Les trois dernières années sont provisoires et révisées chaque printemps par l''INSEE.',
   'DEPENSES', 0, 10000),
  ('INSEE_COMPTES_APU', 'DEPENSES_APU_PIB', 'Dépense publique en part du PIB',
   'Dépense publique rapportée au produit intérieur brut de la même année.',
   'pourcentage', 'taux', '100 × dépense publique / PIB',
   'Un ratio, pas une part : une partie de la dépense (prestations, intérêts) ne passe pas '
   'par la production.',
   'DEPENSES', 20, 80),
  ('INSEE_COMPTES_APU', 'DEPENSE_FONCTION', 'Dépense publique par fonction',
   'Dépenses consolidées des administrations publiques, ventilées selon leur finalité '
   '(nomenclature internationale COFOG, dix grandes fonctions).',
   'milliards_euros', 'flux', NULL,
   'Publiée un an après les autres comptes : la dernière année manque jusqu''en décembre.',
   'DEPENSES', 0, 10000),
  ('INSEE_COMPTES_APU', 'DEPENSE_ETAGE', 'Dépense publique par administration',
   'Part de la dépense publique consolidée réalisée par l''État et les organismes '
   'nationaux, la Sécurité sociale et les collectivités locales.',
   'milliards_euros', 'flux', NULL,
   'Disponible depuis 2009 ; publiée un an après les autres comptes.',
   'DEPENSES', 0, 10000),
  ('INSEE_COMPTES_APU', 'RECETTES_APU', 'Recettes publiques',
   'Recettes consolidées de l''ensemble des administrations publiques : impôts, cotisations '
   'sociales, ventes et autres recettes.',
   'milliards_euros', 'flux', NULL,
   'Les trois dernières années sont provisoires et révisées chaque printemps par l''INSEE.',
   'RECETTES', 0, 10000),
  ('INSEE_COMPTES_APU', 'RECETTES_APU_PIB', 'Recettes publiques en part du PIB',
   'Recettes publiques rapportées au produit intérieur brut de la même année.',
   'pourcentage', 'taux', '100 × recettes publiques / PIB', NULL,
   'RECETTES', 20, 80),
  ('INSEE_COMPTES_APU', 'RECETTE_NATURE', 'Recettes publiques par nature',
   'Recettes des administrations publiques : TVA et autres impôts sur la production, '
   'impôts sur le revenu et le patrimoine (dont CSG), cotisations sociales, autres.',
   'milliards_euros', 'flux', NULL,
   '« Autres » regroupe les ventes, les revenus de la propriété, les impôts en capital '
   '(droits de succession) et les transferts reçus.',
   'RECETTES', 0, 10000),
  ('INSEE_COMPTES_APU', 'PRELEVEMENTS_OBLIGATOIRES', 'Prélèvements obligatoires',
   'Impôts et cotisations sociales effectivement perçus par les administrations publiques '
   'et l''Union européenne, nets des crédits d''impôt.',
   'milliards_euros', 'flux', NULL, NULL,
   'RECETTES', 0, 10000),
  ('INSEE_COMPTES_APU', 'PRELEVEMENTS_PIB', 'Taux de prélèvements obligatoires',
   'Prélèvements obligatoires rapportés au produit intérieur brut.',
   'pourcentage', 'taux', '100 × prélèvements obligatoires / PIB', NULL,
   'RECETTES', 10, 70),
  ('INSEE_COMPTES_APU', 'SOLDE_APU', 'Solde public',
   'Capacité (positive) ou besoin (négatif) de financement des administrations publiques '
   'au sens de Maastricht : recettes moins dépenses. Un solde négatif est un déficit.',
   'milliards_euros', 'flux', 'recettes − dépenses',
   'Le solde de chaque administration n''est pas consolidé : leur somme diffère un peu du '
   'total.',
   'DETTE', -1000, 1000),
  ('INSEE_COMPTES_APU', 'SOLDE_APU_PIB', 'Solde public en part du PIB',
   'Solde public rapporté au produit intérieur brut ; le traité de Maastricht fixe un '
   'déficit d''au plus 3 %.',
   'pourcentage', 'taux', '100 × solde public / PIB', NULL,
   'DETTE', -30, 10),
  ('INSEE_COMPTES_APU', 'DETTE_APU', 'Dette publique',
   'Dette brute des administrations publiques au sens de Maastricht, au 31 décembre, en '
   'valeur nominale.',
   'milliards_euros', 'effectif', NULL,
   'La dette de chaque administration est consolidée au sein de l''ensemble des '
   'administrations publiques.',
   'DETTE', 0, 20000),
  ('INSEE_COMPTES_APU', 'DETTE_APU_PIB', 'Dette publique en part du PIB',
   'Dette publique au 31 décembre rapportée au PIB de l''année ; le traité de Maastricht '
   'fixe un plafond de 60 %.',
   'pourcentage', 'taux', '100 × dette publique / PIB', NULL,
   'DETTE', 0, 300),
  ('INSEE_COMPTES_APU', 'CHARGE_INTERETS', 'Intérêts de la dette',
   'Intérêts versés par les administrations publiques sur leur dette.',
   'milliards_euros', 'flux', NULL,
   'En comptabilité nationale : les intérêts courus de l''année, pas ceux payés.',
   'DETTE', 0, 1000),
  ('INSEE_DETTE_TRIM', 'DETTE_TRIMESTRIELLE', 'Dette publique, dernier trimestre',
   'Dette brute des administrations publiques au sens de Maastricht en fin de trimestre.',
   'milliards_euros', 'effectif', NULL,
   'Publiée trois mois après la fin du trimestre ; révisée avec les comptes annuels.',
   'DETTE', 0, 20000),
  ('INSEE_DETTE_TRIM', 'DETTE_TRIMESTRIELLE_PIB', 'Dette publique en part du PIB, dernier trimestre',
   'Dette publique en fin de trimestre rapportée au PIB des quatre derniers trimestres.',
   'pourcentage', 'taux', '100 × dette / PIB des quatre derniers trimestres', NULL,
   'DETTE', 0, 300)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement, theme,
        borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;
