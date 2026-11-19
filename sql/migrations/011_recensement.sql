-- Phase 2 : recensement de la population, statut d'activité déclaré (INSEE, Melodi).

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('statut_activite', 'ACTIF', 'Actifs (en emploi ou au chômage)'),
  ('statut_activite', 'ACTIF_OCCUPE', 'Actifs en emploi'),
  ('statut_activite', 'CHOMEUR', 'Chômeurs déclarés'),
  ('statut_activite', 'INACTIF', 'Inactifs'),
  ('statut_activite', 'RETRAITE', 'Retraités ou préretraités déclarés'),
  ('statut_activite', 'ETUDIANT', 'Élèves, étudiants, stagiaires non rémunérés'),
  ('statut_activite', 'AUTRE_INACTIF', 'Autres inactifs, dont personnes au foyer');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       'Statut déclaré par les personnes recensées, différent du chômage au sens du BIT '
       'et du nombre de pensionnés des caisses de retraite.',
       'Millésime = moyenne de 5 enquêtes annuelles : ne comparer que des millésimes '
       'séparés d''au moins 5 ans (ex. 2017 et 2023 ; 2024 est une année blanche).'
FROM ref.source s
CROSS JOIN (VALUES
  ('POP_RP', 'Population recensée par statut d''activité',
   'Population de 15 ans ou plus selon le statut d''activité déclaré au recensement.',
   'personnes', 'effectif', NULL),
  ('ACTIFS_15_64', 'Actifs de 15 à 64 ans',
   'Personnes de 15 à 64 ans en emploi ou au chômage (déclaré au recensement).',
   'personnes', 'effectif', 'population de 15 à 64 ans, statut « actif »'),
  ('INACTIFS_15_64', 'Inactifs de 15 à 64 ans',
   'Personnes de 15 à 64 ans ni en emploi ni au chômage : étudiants, retraités, '
   'personnes au foyer…',
   'personnes', 'effectif', 'population de 15 à 64 ans, statut « inactif »'),
  ('RETRAITES_RP', 'Retraités déclarés',
   'Personnes de 15 ans ou plus se déclarant retraitées ou préretraitées au recensement.',
   'personnes', 'effectif', 'population de 15 ans ou plus, statut « retraité »'),
  ('TAUX_ACTIVITE_15_64', 'Taux d''activité des 15-64 ans',
   'Part des actifs (en emploi ou au chômage) dans la population de 15 à 64 ans.',
   'pourcentage', 'taux', '100 × actifs de 15 à 64 ans / population de 15 à 64 ans')
) AS v (code, libelle, definition, unite, nature, formule)
WHERE s.code = 'INSEE_RP';

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
WHERE v.valeur IS NOT NULL;
