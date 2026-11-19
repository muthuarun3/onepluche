-- Phase 2 : taux de chômage localisés (INSEE, BDM), trimestriels.

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id,
                            avertissement, comparabilite)
SELECT 'TAUX_CHOMAGE', 'Taux de chômage localisé',
       'Chômeurs au sens du BIT pour 100 actifs, en moyenne trimestrielle, corrigé des '
       'variations saisonnières.',
       'pourcentage', 'taux', source_id,
       'Les derniers trimestres sont provisoires et révisés à chaque publication. '
       'France : hors Mayotte (Guyane comprise depuis 2014).',
       'Comparable entre territoires et dans le temps (estimations cohérentes avec le '
       'taux national de l''enquête Emploi).'
FROM ref.source WHERE code = 'INSEE_CHOM';

-- Séries infra-annuelles : chaque valeur porte sa période exacte (colonnes ajoutées en fin).
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
WHERE n.sexe = 'T' AND n.age_min IS NULL AND n.age_max IS NULL AND n.modalite_id IS NULL;
