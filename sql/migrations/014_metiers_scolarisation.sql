-- Qui sont les Français ? Étape 1 : catégories socioprofessionnelles, secteurs d'activité
-- et scolarisation (INSEE, recensement), et vue des répartitions par modalité.

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('pcs', 'AGRICULTEURS', 'Agriculteurs exploitants'),
  ('pcs', 'ARTISANS_COMMERCANTS', 'Artisans, commerçants, chefs d''entreprise'),
  ('pcs', 'CADRES', 'Cadres et professions intellectuelles supérieures'),
  ('pcs', 'PROF_INTERMEDIAIRES', 'Professions intermédiaires'),
  ('pcs', 'EMPLOYES', 'Employés'),
  ('pcs', 'OUVRIERS', 'Ouvriers'),
  ('pcs', 'RETRAITES', 'Retraités'),
  ('pcs', 'AUTRES_SANS_ACTIVITE', 'Autres personnes sans activité professionnelle'),
  ('secteur', 'AGRICULTURE', 'Agriculture'),
  ('secteur', 'INDUSTRIE', 'Industrie'),
  ('secteur', 'CONSTRUCTION', 'Construction'),
  ('secteur', 'COMMERCE_SERVICES', 'Commerce, transports et services divers'),
  ('secteur', 'ADMIN_ENSEIGNEMENT_SANTE',
   'Administration publique, enseignement, santé et action sociale'),
  ('scolarisation', 'SCOLARISE', 'Élèves, étudiants ou apprentis scolarisés');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement,
       'Millésime = moyenne de 5 enquêtes annuelles : ne comparer que des millésimes '
       'séparés d''au moins 5 ans (ex. 2017 et 2023 ; 2024 est une année blanche).'
FROM ref.source s
CROSS JOIN (VALUES
  ('POP_PCS', 'Population de 15 ans ou plus par catégorie socioprofessionnelle',
   'Personnes de 15 ans ou plus selon le groupe socioprofessionnel déclaré au '
   'recensement : métier actuel, ou dernier métier exercé pour les chômeurs.',
   'personnes', 'effectif', NULL,
   'Les retraités forment un groupe à part, quel que soit leur ancien métier.'),
  ('EMPLOIS_RP', 'Actifs en emploi par secteur d''activité',
   'Personnes de 15 ans ou plus ayant un emploi, selon le secteur d''activité de '
   'l''établissement qui les emploie, au lieu de résidence.',
   'personnes', 'effectif', NULL,
   'Disponible pour le millésime 2023 seulement.'),
  ('POP_SCOLARISATION', 'Population selon la scolarisation',
   'Personnes de 2 ans ou plus, par tranche d''âge, et parmi elles celles inscrites '
   'dans un établissement d''enseignement (élèves, étudiants, apprentis).',
   'personnes', 'effectif', NULL,
   'Au lieu de résidence, déclaré au recensement.'),
  ('TAUX_SCOLARISATION_18_24', 'Taux de scolarisation des 18-24 ans',
   'Part des 18-24 ans inscrits dans un établissement d''enseignement (études '
   'supérieures, lycée ou apprentissage).',
   'pourcentage', 'taux', '100 × scolarisés de 18 à 24 ans / population de 18 à 24 ans',
   'Au lieu de résidence, déclaré au recensement.')
) AS v (code, libelle, definition, unite, nature, formule, avertissement)
WHERE s.code = 'INSEE_RP';

-- Répartition d'un effectif entre les modalités d'une dimension (catégories
-- socioprofessionnelles, secteurs, statut d'activité…), avec le total pour calculer
-- les parts. Tous sexes confondus.
CREATE VIEW api.repartition AS
SELECT i.code AS indicateur,
       m.dimension,
       m.code AS modalite,
       m.libelle,
       m.modalite_id AS ordre,
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int AS annee,
       o.periode_type,
       o.age_min,
       o.age_max,
       o.valeur,
       tot.valeur AS total,
       o.statut = 'PROVISOIRE' AS provisoire
FROM stat.observation o
JOIN ref.modalite m USING (modalite_id)
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
LEFT JOIN stat.observation tot
  ON tot.indicateur_id = o.indicateur_id
 AND tot.territoire_id = o.territoire_id
 AND tot.periode = o.periode
 AND tot.sexe = o.sexe
 AND tot.age_min IS NOT DISTINCT FROM o.age_min
 AND tot.age_max IS NOT DISTINCT FROM o.age_max
 AND tot.modalite_id IS NULL
WHERE o.sexe = 'T';

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
WHERE s.sexe = 'T' AND s.age_min = 18 AND s.age_max = 24;
