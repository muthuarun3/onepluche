-- Appli « Comment vivent les Français ? » (rubrique /vivre), phase A2 : séries nationales.
-- Salaire moyen du privé depuis 1996, niveau de vie et inégalités depuis 1996 (ERFS),
-- comptes des ménages (pouvoir d'achat, revenu disponible, épargne), patrimoine (enquête
-- 2024 et placements financiers) et pension moyenne (DREES). Dossier de conception, étapes
-- 5 et 6 (validées le 22/11/2026) : les séries nationales gardent un code à part (_SERIE)
-- pour ne pas être comparées aux chiffres départementaux de Filosofi.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_ERFS', 'INSEE',
   'Enquête Revenus fiscaux et sociaux : séries rétropolées du niveau de vie',
   'https://www.insee.fr/fr/metadonnees/source/serie/s1231'),
  ('INSEE_ENQPAT', 'INSEE',
   'Enquête Histoire de vie et Patrimoine : patrimoine des ménages',
   'https://www.insee.fr/fr/metadonnees/source/serie/s1005');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  -- Catégorie de la personne de référence du ménage (enquête Patrimoine).
  ('pcs', 'PROFESSIONS_LIBERALES', 'Professions libérales'),
  ('pcs', 'CADRES_HORS_LIBERALES', 'Cadres (hors professions libérales)'),
  ('pcs', 'RETRAITES_INDEPENDANTS',
   'Retraités anciens agriculteurs, artisans, commerçants ou chefs d''entreprise'),
  ('pcs', 'RETRAITES_CADRES', 'Retraités anciens cadres ou professions libérales'),
  ('pcs', 'RETRAITES_PROF_INTERMEDIAIRES', 'Retraités anciennes professions intermédiaires'),
  ('pcs', 'RETRAITES_EMPLOYES_OUVRIERS', 'Retraités anciens employés ou ouvriers'),
  ('pcs', 'INACTIFS_JAMAIS_TRAVAILLE', 'Inactifs n''ayant jamais travaillé'),
  -- Décile de niveau de vie du ménage.
  ('decile_niveau_vie', 'D01', '10 % les plus modestes'),
  ('decile_niveau_vie', 'D02', '2e dixième'),
  ('decile_niveau_vie', 'D03', '3e dixième'),
  ('decile_niveau_vie', 'D04', '4e dixième'),
  ('decile_niveau_vie', 'D05', '5e dixième'),
  ('decile_niveau_vie', 'D06', '6e dixième'),
  ('decile_niveau_vie', 'D07', '7e dixième'),
  ('decile_niveau_vie', 'D08', '8e dixième'),
  ('decile_niveau_vie', 'D09', '9e dixième'),
  ('decile_niveau_vie', 'D10', '10 % les plus aisés'),
  -- Placements financiers des ménages (comptes de patrimoine).
  ('placement', 'DEPOTS', 'Numéraire et dépôts (comptes courants, livrets, épargne logement)'),
  ('placement', 'TITRES_CREANCE', 'Titres de créance (obligations)'),
  ('placement', 'ACTIONS', 'Actions et autres participations'),
  ('placement', 'FONDS', 'Parts de fonds d''investissement'),
  ('placement', 'ASSURANCE_VIE', 'Assurance vie et rentes');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, rubrique, theme, borne_min, borne_max,
                            seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, NULL,
       v.avertissement, 'VIVRE', v.theme, v.borne_min, v.borne_max, v.seuil
FROM (VALUES
  -- Revenus.
  ('INSEE_BTS', 'SALAIRE_PRIVE_SERIE', 'Salaire net mensuel moyen du privé depuis 1996',
   'Salaire net de prélèvements sociaux, en équivalent temps plein, par mois, des salariés '
   'du secteur privé, en euros constants de la dernière année publiée : l''inflation est '
   'retirée, les années se comparent directement. Par sexe.',
   'euros', 'ratio',
   'France métropolitaine jusqu''en 1999, France ensuite. Hors salariés agricoles et '
   'salariés des particuliers employeurs.',
   'REVENUS', 1000, 9000, 0.15),
  -- Pouvoir d'achat (comptes nationaux).
  ('INSEE_CNA', 'POUVOIR_ACHAT_UC', 'Évolution du pouvoir d''achat par unité de consommation',
   'Évolution sur un an du revenu disponible brut des ménages, corrigée de la hausse des prix '
   'et ramenée au nombre d''unités de consommation (une pour le premier adulte, 0,5 par '
   'personne de 14 ans ou plus, 0,3 par enfant). Ce qui reste au ménage moyen, une fois la '
   'croissance de la population prise en compte.',
   'pourcentage', 'taux',
   'Moyenne de tous les ménages : une hausse moyenne peut cacher des baisses pour une '
   'partie d''entre eux. Les deux dernières années sont provisoires.',
   'POUVOIR_ACHAT', -15, 15, NULL),
  ('INSEE_CNA', 'REVENU_DISPONIBLE', 'Revenu disponible brut des ménages',
   'Revenus d''activité, du patrimoine et prestations sociales reçus par l''ensemble des '
   'ménages, moins les impôts et cotisations versés, en millions d''euros courants.',
   'millions_euros', 'flux', 'Les deux dernières années sont provisoires.',
   'POUVOIR_ACHAT', 1000, 5000000, 0.1),
  -- Épargne (comptes nationaux).
  ('INSEE_CNA', 'TAUX_EPARGNE', 'Taux d''épargne des ménages',
   'Part du revenu disponible brut que les ménages ne consomment pas : épargne financière, '
   'remboursement du capital des emprunts immobiliers et investissement dans le logement.',
   'pourcentage', 'taux', 'Les deux dernières années sont provisoires.',
   'EPARGNE', 0, 40, NULL),
  ('INSEE_CNA', 'TAUX_EPARGNE_FINANCIERE', 'Taux d''épargne financière des ménages',
   'Part du revenu disponible brut placée en produits financiers (livrets, assurance vie, '
   'actions…) ou utilisée pour se désendetter, une fois l''investissement immobilier déduit.',
   'pourcentage', 'taux', 'Les deux dernières années sont provisoires.',
   'EPARGNE', -10, 30, NULL),
  -- Inégalités (enquête Revenus fiscaux et sociaux).
  ('INSEE_ERFS', 'NIVEAU_VIE_MEDIAN_SERIE', 'Niveau de vie médian depuis 1996',
   'Niveau de vie annuel qui partage les personnes en deux moitiés, en euros constants de '
   'la dernière année publiée.',
   'euros', 'ratio', NULL, 'INEGALITES', 10000, 50000, 0.15),
  ('INSEE_ERFS', 'TAUX_PAUVRETE_SERIE', 'Taux de pauvreté depuis 1996',
   'Part des personnes dont le niveau de vie est inférieur à 60 % du niveau de vie médian.',
   'pourcentage', 'taux', NULL, 'INEGALITES', 5, 30, NULL),
  ('INSEE_ERFS', 'GINI_SERIE', 'Indice de Gini du niveau de vie depuis 1996',
   'Mesure des inégalités de niveau de vie, de 0 (tous égaux) à 1 (une seule personne '
   'détient tout).',
   'ratio', 'ratio', NULL, 'INEGALITES', 0.15, 0.6, NULL),
  ('INSEE_ERFS', 'RAPPORT_D9_D1_SERIE', 'Rapport D9/D1 depuis 1996',
   'Niveau de vie du 9e décile divisé par celui du 1er décile.',
   'ratio', 'ratio', NULL, 'INEGALITES', 1.5, 10, NULL),
  -- Patrimoine.
  ('INSEE_ENQPAT', 'PATRIMOINE_BRUT_MOYEN', 'Patrimoine brut moyen des ménages',
   'Valeur moyenne de ce que possède un ménage (logements, placements financiers, biens '
   'professionnels, voitures, objets de valeur…), avant déduction des emprunts. Selon l''âge '
   'et la catégorie de la personne de référence, et selon le niveau de vie du ménage.',
   'euros', 'ratio',
   'Moyenne tirée vers le haut par les plus gros patrimoines : la moitié des ménages possède '
   'bien moins.',
   'PATRIMOINE', 1000, 10000000, NULL),
  ('INSEE_ENQPAT', 'PATRIMOINE_NET_MEDIAN', 'Patrimoine net médian des ménages',
   'Patrimoine, emprunts déduits, qui partage les ménages en deux moitiés.',
   'euros', 'ratio', NULL, 'PATRIMOINE', 10000, 1000000, NULL),
  ('INSEE_CNA', 'PATRIMOINE_FINANCIER', 'Placements financiers des ménages',
   'Encours, en fin d''année, des placements financiers de l''ensemble des ménages, en '
   'millions d''euros courants : dépôts et livrets, obligations, actions, fonds, assurance '
   'vie.',
   'millions_euros', 'effectif', 'La dernière année est provisoire.',
   'PATRIMOINE', 0, 20000000, 0.15),
  -- Retraites (DREES).
  ('DREES_PENS', 'PENSION_MOYENNE', 'Pension de retraite moyenne',
   'Montant brut mensuel moyen de la pension de droit direct (y compris la majoration pour '
   'trois enfants ou plus), tous régimes, des retraités résidant en France, en euros '
   'courants. Par sexe.',
   'euros', 'ratio',
   'Pension de droit direct seule : hors pension de réversion versée au conjoint survivant.',
   'RETRAITES', 300, 5000, 0.15)
) AS v (source, code, libelle, definition, unite, nature, avertissement, theme, borne_min,
        borne_max, seuil)
JOIN ref.source s ON s.code = v.source;

UPDATE ref.indicateur
SET comparabilite = 'France métropolitaine seulement, enquête Revenus fiscaux et sociaux : '
                    'ses valeurs diffèrent de celles de Filosofi pour la même année, elles ne '
                    'se comparent pas aux chiffres départementaux.'
WHERE code IN ('NIVEAU_VIE_MEDIAN_SERIE', 'TAUX_PAUVRETE_SERIE', 'GINI_SERIE',
               'RAPPORT_D9_D1_SERIE');

UPDATE ref.indicateur
SET comparabilite = 'Enquête 2023-2024, France hors Mayotte. L''enquête a lieu tous les '
                    'trois ans environ.'
WHERE code IN ('PATRIMOINE_BRUT_MOYEN', 'PATRIMOINE_NET_MEDIAN');
