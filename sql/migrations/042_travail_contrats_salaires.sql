-- Appli « Comment travaillent les Français ? », PR T4 : thèmes « Comment » (contrats courts,
-- temps partiel, recensement 2023) et « Combien ça paie ». Les salaires de la Base Tous
-- salariés sont déjà importés par l'appli « Comment vivent les Français ? »
-- (SALAIRE_NET_MOYEN) : on les affiche dans la rubrique sans les réimporter, comme le taux
-- de chômage trimestriel de l'appli 1. Dossier de conception de l'appli travail, étape 5.

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme,
                            borne_min, borne_max)
SELECT v.code, v.libelle, v.definition, 'pourcentage', 'taux', s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'TRAVAIL', 'CONDITIONS', 0, v.borne_max
FROM (VALUES
  ('PART_CONTRATS_COURTS', 'Part des contrats courts',
   'Salariés en CDD, intérim, apprentissage, stage ou contrat aidé, pour 100 salariés, '
   'parmi les personnes en emploi qui habitent le territoire. Par sexe et âge.',
   '100 × autres contrats / (emplois à durée indéterminée + autres contrats)',
   'Recensement : moyenne de cinq enquêtes annuelles (2021 à 2025 pour le millésime 2023). '
   'Hors Mayotte. Les jeunes sont souvent en apprentissage ou en stage, comptés ici.',
   'Comparable entre territoires ; ne comparer deux millésimes qu''à cinq ans d''écart.', 90),
  ('PART_TEMPS_PARTIEL', 'Part du temps partiel',
   'Personnes à temps partiel pour 100 personnes en emploi (salariées ou non), parmi celles '
   'qui habitent le territoire. Par sexe et âge.',
   '100 × temps partiel / personnes en emploi',
   'Recensement : moyenne de cinq enquêtes annuelles. Hors Mayotte. Le temps partiel est '
   'déclaré par la personne, choisi ou subi.',
   'Comparable entre territoires ; ne comparer deux millésimes qu''à cinq ans d''écart.', 80)
) AS v (code, libelle, definition, formule, avertissement, comparabilite, borne_max)
CROSS JOIN ref.source s
WHERE s.code = 'INSEE_RP';

INSERT INTO ref.indicateur_affichage (indicateur_id, rubrique, theme, ordre)
SELECT i.indicateur_id, 'TRAVAIL', v.theme, v.ordre
FROM (VALUES
  ('TAUX_CHOMAGE', 'CHERCHER_CREER', 1),
  ('SALAIRE_NET_MOYEN', 'SALAIRES', 1)
) AS v (code, theme, ordre)
JOIN ref.indicateur i ON i.code = v.code;
