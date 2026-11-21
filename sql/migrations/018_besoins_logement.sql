-- Appli 2, phase B : logement (recensement, revenus Filosofi). Dossier de conception de
-- l'appli 2, étape 5. Le combustible principal des résidences principales vient du même
-- jeu du recensement ; il est rangé dans le thème énergie.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_FILOSOFI', 'INSEE',
   'Revenus localisés sociaux et fiscaux (Filosofi) : niveau de vie et pauvreté',
   'https://www.insee.fr/fr/metadonnees/source/serie/s1172');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('categorie_logement', 'RESIDENCE_PRINCIPALE', 'Résidences principales'),
  ('categorie_logement', 'RESIDENCE_SECONDAIRE',
   'Résidences secondaires et logements occasionnels'),
  ('categorie_logement', 'VACANT', 'Logements vacants'),
  ('statut_occupation', 'PROPRIETAIRE', 'Propriétaires'),
  ('statut_occupation', 'LOCATAIRE', 'Locataires (tous)'),
  ('statut_occupation', 'LOCATAIRE_PRIVE', 'Locataires d''un logement vide du parc privé'),
  ('statut_occupation', 'LOCATAIRE_HLM', 'Locataires d''un logement vide du parc social (HLM)'),
  ('statut_occupation', 'LOCATAIRE_MEUBLE', 'Locataires d''un logement meublé'),
  ('statut_occupation', 'LOGE_GRATUIT', 'Logés gratuitement'),
  ('combustible', 'ELECTRICITE', 'Électricité'),
  ('combustible', 'GAZ_RESEAU', 'Gaz de ville ou réseau de chaleur'),
  ('combustible', 'GAZ_BOUTEILLE', 'Gaz en bouteille ou en citerne'),
  ('combustible', 'FIOUL', 'Fioul (mazout)'),
  ('combustible', 'AUTRE', 'Autres (bois, solaire, géothermie…)');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, NULL, 'BESOINS', v.theme, v.angle,
       v.borne_min, v.borne_max, v.seuil_variation
FROM (VALUES
  ('INSEE_RP', 'LOGEMENTS', 'Logements par catégorie',
   'Logements recensés : résidences principales, résidences secondaires et logements '
   'occasionnels, logements vacants.',
   'logements', 'effectif', NULL, NULL, 'LOGEMENT', NULL, NULL, NULL, NULL),
  ('INSEE_RP', 'RESIDENCES_PRINC', 'Résidences principales par statut d''occupation',
   'Logements occupés à titre de résidence principale, selon que le ménage est '
   'propriétaire, locataire (parc privé, parc social, meublé) ou logé gratuitement.',
   'logements', 'effectif', NULL, NULL, 'LOGEMENT', NULL, NULL, NULL, NULL),
  ('INSEE_RP', 'RESIDENCES_PRINC_CHAUFFAGE',
   'Résidences principales par combustible principal',
   'Résidences principales selon le combustible principal du chauffage. Hors Mayotte '
   'et hors outre-mer, où la question n''est pas posée.',
   'logements', 'effectif', NULL, NULL, 'ENERGIE', NULL, NULL, NULL, NULL),
  ('INSEE_RP', 'PART_PROPRIETAIRES', 'Part de ménages propriétaires',
   'Part des résidences principales occupées par leur propriétaire.',
   'pourcentage', 'taux', '100 × résidences principales occupées par un propriétaire / '
   'résidences principales', NULL, 'LOGEMENT', 'ACCES', 0, 100, NULL),
  ('INSEE_RP', 'PART_LOCATAIRES_HLM', 'Part de ménages locataires HLM',
   'Part des résidences principales louées vides dans le parc social (HLM).',
   'pourcentage', 'taux', '100 × résidences principales louées vides en HLM / '
   'résidences principales', NULL, 'LOGEMENT', 'ACCES', 0, 100, NULL),
  ('INSEE_RP', 'PART_LOGEMENTS_VACANTS', 'Part de logements vacants',
   'Part des logements inoccupés (à vendre, à louer, en attente, sans affectation).',
   'pourcentage', 'taux', '100 × logements vacants / logements', NULL, 'LOGEMENT', 'MANQUE',
   0, 100, NULL),
  ('INSEE_RP', 'PART_CHAUFFAGE_FIOUL', 'Part de résidences principales chauffées au fioul',
   'Part des résidences principales dont le combustible principal est le fioul.',
   'pourcentage', 'taux', '100 × résidences principales chauffées au fioul / résidences '
   'principales', NULL, 'ENERGIE', 'ACCES', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'NIVEAU_VIE_MEDIAN', 'Niveau de vie médian',
   'Niveau de vie annuel au-dessus duquel se situe la moitié des personnes : revenu '
   'disponible du ménage après impôts et prestations, divisé par le nombre d''unités de '
   'consommation (1 pour le premier adulte, 0,5 par autre personne de 14 ans ou plus, '
   '0,3 par enfant). Par tranche d''âge et statut d''occupation de la personne de '
   'référence du ménage.',
   'euros', 'ratio', NULL,
   'Un niveau de vie n''est pas un salaire : c''est un revenu par unité de consommation.',
   'LOGEMENT', NULL, 5000, 80000, 0.15),
  ('INSEE_FILOSOFI', 'TAUX_PAUVRETE', 'Taux de pauvreté',
   'Part des personnes dont le niveau de vie est inférieur à 60 % du niveau de vie '
   'médian de la France métropolitaine. Par tranche d''âge et statut d''occupation de '
   'la personne de référence du ménage.',
   'pourcentage', 'taux', NULL, NULL, 'LOGEMENT', 'MANQUE', 0, 100, NULL)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement, theme,
        angle, borne_min, borne_max, seuil_variation)
JOIN ref.source s ON s.code = v.source;

-- Avertissement commun aux indicateurs du recensement (même règle que l'appli 1).
UPDATE ref.indicateur
SET comparabilite = 'Millésime = moyenne de 5 enquêtes annuelles : ne comparer que des '
                    'millésimes séparés d''au moins 5 ans (ex. 2017 et 2023).'
WHERE code IN ('LOGEMENTS', 'RESIDENCES_PRINC', 'RESIDENCES_PRINC_CHAUFFAGE',
               'PART_PROPRIETAIRES', 'PART_LOCATAIRES_HLM', 'PART_LOGEMENTS_VACANTS',
               'PART_CHAUFFAGE_FIOUL');

-- Indicateurs calculés de l'appli 2 : une seule vue, remplacée à chaque nouveau thème,
-- et ajoutée une fois pour toutes à api.serie.
CREATE VIEW stat.besoins_derives AS
WITH part AS (
  -- Part d'une modalité dans le total de la même série (même indicateur, territoire,
  -- période, sans tranche d'âge).
  SELECT d.code AS indicateur, o.territoire_id, o.periode, o.periode_type,
         o.statut = 'PROVISOIRE' AS provisoire,
         round(100 * o.valeur / nullif(tot.valeur, 0), 1) AS valeur
  FROM (VALUES
    ('PART_PROPRIETAIRES', 'RESIDENCES_PRINC', 'statut_occupation', 'PROPRIETAIRE'),
    ('PART_LOCATAIRES_HLM', 'RESIDENCES_PRINC', 'statut_occupation', 'LOCATAIRE_HLM'),
    ('PART_LOGEMENTS_VACANTS', 'LOGEMENTS', 'categorie_logement', 'VACANT'),
    ('PART_CHAUFFAGE_FIOUL', 'RESIDENCES_PRINC_CHAUFFAGE', 'combustible', 'FIOUL')
  ) AS d (code, base, dimension, modalite)
  JOIN ref.indicateur i ON i.code = d.base
  JOIN ref.modalite m ON m.dimension = d.dimension AND m.code = d.modalite
  JOIN stat.observation o
    ON o.indicateur_id = i.indicateur_id AND o.modalite_id = m.modalite_id
   AND o.sexe = 'T' AND o.age_min IS NULL AND o.age_max IS NULL
  JOIN stat.observation tot
    ON tot.indicateur_id = o.indicateur_id AND tot.territoire_id = o.territoire_id
   AND tot.periode = o.periode AND tot.sexe = 'T'
   AND tot.age_min IS NULL AND tot.age_max IS NULL AND tot.modalite_id IS NULL
)
SELECT p.indicateur, t.niveau, t.code, extract(year FROM p.periode)::int AS annee,
       p.valeur, p.provisoire, 'T'::char(1) AS sexe, p.periode, p.periode_type
FROM part p
JOIN ref.territoire t USING (territoire_id)
WHERE p.valeur IS NOT NULL;

CREATE OR REPLACE VIEW api.serie AS
SELECT v.indicateur,
       t.niveau,
       t.code,
       extract(year FROM s.periode)::int AS annee,
       v.valeur,
       s.provisoire,
       'T'::char(1) AS sexe,
       s.periode,
       '1ER_JANVIER'::text AS periode_type
FROM stat.structure_age s
JOIN ref.territoire t USING (territoire_id)
CROSS JOIN LATERAL (VALUES
  ('POP', s.population),
  ('PART_MOINS_20', round(100 * s.moins_20 / nullif(s.population, 0), 2)),
  ('PART_60_PLUS', round(100 * s.plus_60 / nullif(s.population, 0), 2)),
  ('PART_75_PLUS', round(100 * s.plus_75 / nullif(s.population, 0), 2)),
  ('INDICE_VIEILLISSEMENT', round(100 * s.plus_65 / nullif(s.moins_20, 0), 1))
) AS v (indicateur, valeur)
WHERE v.valeur IS NOT NULL
UNION ALL
-- Indicateurs publiés tels quels par la source (hors population, déjà ci-dessus).
SELECT i.code,
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int,
       o.valeur,
       o.statut = 'PROVISOIRE',
       o.sexe,
       o.periode,
       o.periode_type
FROM stat.observation o
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
WHERE i.code <> 'POP'
  AND o.age_min IS NULL AND o.age_max IS NULL AND o.modalite_id IS NULL
UNION ALL
SELECT 'SOLDE_NATUREL',
       t.niveau,
       t.code,
       extract(year FROM n.periode)::int,
       n.valeur - d.valeur,
       n.statut = 'PROVISOIRE' OR d.statut = 'PROVISOIRE',
       'T',
       n.periode,
       n.periode_type
FROM stat.observation n
JOIN ref.indicateur ni ON ni.indicateur_id = n.indicateur_id AND ni.code = 'NAISSANCES'
JOIN stat.observation d
  ON d.territoire_id = n.territoire_id AND d.periode = n.periode AND d.sexe = n.sexe
 AND d.age_min IS NULL AND d.age_max IS NULL AND d.modalite_id IS NULL
JOIN ref.indicateur di ON di.indicateur_id = d.indicateur_id AND di.code = 'DECES'
JOIN ref.territoire t ON t.territoire_id = n.territoire_id
WHERE n.sexe = 'T' AND n.age_min IS NULL AND n.age_max IS NULL AND n.modalite_id IS NULL
UNION ALL
-- Recensement : effectifs et taux d'activité déduits de la population par statut d'activité.
SELECT v.indicateur,
       t.niveau,
       t.code,
       extract(year FROM r.periode)::int,
       v.valeur,
       false,
       'T',
       r.periode,
       'RP'
FROM (
  SELECT o.territoire_id,
         o.periode,
         sum(o.valeur) FILTER (WHERE o.age_max = 64 AND m.code IS NULL) AS pop_15_64,
         sum(o.valeur) FILTER (WHERE o.age_max = 64 AND m.code = 'ACTIF') AS actifs,
         sum(o.valeur) FILTER (WHERE o.age_max = 64 AND m.code = 'INACTIF') AS inactifs,
         sum(o.valeur) FILTER (WHERE o.age_max IS NULL AND m.code = 'RETRAITE') AS retraites
  FROM stat.observation o
  JOIN ref.indicateur i USING (indicateur_id)
  LEFT JOIN ref.modalite m USING (modalite_id)
  WHERE i.code = 'POP_RP' AND o.sexe = 'T' AND o.age_min = 15
  GROUP BY o.territoire_id, o.periode
) r
JOIN ref.territoire t USING (territoire_id)
CROSS JOIN LATERAL (VALUES
  ('ACTIFS_15_64', round(r.actifs)),
  ('INACTIFS_15_64', round(r.inactifs)),
  ('RETRAITES_RP', round(r.retraites)),
  ('TAUX_ACTIVITE_15_64', round(100 * r.actifs / nullif(r.pop_15_64, 0), 1))
) AS v (indicateur, valeur)
WHERE v.valeur IS NOT NULL
UNION ALL
-- Retraités pour 100 actifs : pensionnés (DREES, national) rapportés aux actifs de 15 à
-- 64 ans du recensement de la même année.
SELECT 'PENSIONNES_POUR_100_ACTIFS',
       t.niveau,
       t.code,
       extract(year FROM p.periode)::int,
       round(100 * p.valeur / nullif(a.actifs, 0), 1),
       p.statut = 'PROVISOIRE',
       'T',
       p.periode,
       'RP'
FROM stat.observation p
JOIN ref.indicateur pi ON pi.indicateur_id = p.indicateur_id AND pi.code = 'PENSIONNES'
JOIN (
  SELECT o.territoire_id, o.periode, sum(o.valeur) AS actifs
  FROM stat.observation o
  JOIN ref.indicateur i USING (indicateur_id)
  JOIN ref.modalite m USING (modalite_id)
  WHERE i.code = 'POP_RP' AND o.sexe = 'T' AND o.age_min = 15 AND o.age_max = 64
    AND m.code = 'ACTIF'
  GROUP BY o.territoire_id, o.periode
) a ON a.territoire_id = p.territoire_id AND a.periode = p.periode
JOIN ref.territoire t ON t.territoire_id = p.territoire_id
WHERE p.sexe = 'T' AND p.age_min IS NULL AND p.age_max IS NULL AND p.modalite_id IS NULL
UNION ALL
-- Taux de scolarisation des 18-24 ans (recensement).
SELECT 'TAUX_SCOLARISATION_18_24',
       t.niveau,
       t.code,
       extract(year FROM s.periode)::int,
       round(100 * s.valeur / nullif(p.valeur, 0), 1),
       false,
       'T',
       s.periode,
       'RP'
FROM stat.observation s
JOIN ref.indicateur i ON i.indicateur_id = s.indicateur_id AND i.code = 'POP_SCOLARISATION'
JOIN ref.modalite m ON m.modalite_id = s.modalite_id AND m.code = 'SCOLARISE'
JOIN stat.observation p
  ON p.indicateur_id = s.indicateur_id AND p.territoire_id = s.territoire_id
 AND p.periode = s.periode AND p.sexe = s.sexe
 AND p.age_min = 18 AND p.age_max = 24 AND p.modalite_id IS NULL
JOIN ref.territoire t ON t.territoire_id = s.territoire_id
WHERE s.sexe = 'T' AND s.age_min = 18 AND s.age_max = 24
UNION ALL
-- Appli 2 : indicateurs calculés de la rubrique « besoins ».
SELECT indicateur, niveau, code, annee, valeur, provisoire, sexe, periode, periode_type
FROM stat.besoins_derives;
