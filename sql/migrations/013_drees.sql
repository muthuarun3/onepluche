-- Phase 2 : retraités (DREES, enquête auprès des caisses de retraite) et allocataires du
-- minimum vieillesse (DREES, panorama statistique).

UPDATE ref.source
SET libelle = 'Retraités tous régimes (enquête annuelle auprès des caisses de retraite)',
    url = 'https://data.drees.solidarites-sante.gouv.fr/explore/dataset/donnes_eacr/'
WHERE code = 'DREES_PENS';

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('DREES_ASPA', 'DREES', 'Allocataires du minimum vieillesse (panorama statistique)',
   'https://data.drees.solidarites-sante.gouv.fr/explore/dataset/panorama-statistique-toutes-thematiques/');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite
FROM ref.source s
JOIN (VALUES
  ('DREES_PENS', 'PENSIONNES', 'Retraités (pensionnés)',
   'Personnes résidant en France percevant une pension de retraite de droit direct ou de '
   'réversion, d''au moins un régime, au 31 décembre ; chaque personne comptée une fois.',
   'personnes', 'effectif', NULL,
   'France entière seulement : la DREES ne publie pas chaque année les retraités par '
   'département. Années sans échantillon interrégimes (EIR, tous les 4 ans) : estimation '
   'DREES par le modèle Ancêtre. Au niveau local, voir les retraités déclarés au recensement.',
   'Comparable dans le temps (série recalée sur les EIR 2004 à 2020).'),
  ('DREES_PENS', 'PENSIONNES_DROIT_DIRECT', 'Retraités de droit direct',
   'Personnes résidant en France percevant une pension acquise en contrepartie de leur '
   'propre activité (hors réversion seule), au 31 décembre.',
   'personnes', 'effectif', NULL,
   'France entière seulement. Années hors EIR : estimation DREES (modèle Ancêtre).',
   'Comparable dans le temps (série recalée sur les EIR 2004 à 2020).'),
  ('DREES_PENS', 'PENSIONNES_POUR_100_ACTIFS', 'Retraités pour 100 actifs',
   'Nombre de retraités (pensionnés) pour 100 actifs de 15 à 64 ans.',
   'ratio', 'ratio',
   '100 × pensionnés au 31 décembre / actifs de 15 à 64 ans du recensement de la même année',
   'France entière, années de recensement seulement. Rapport démographique approché : '
   'les actifs du recensement incluent les chômeurs et excluent les actifs de 65 ans ou plus.',
   'Ne comparer que des millésimes du recensement séparés d''au moins 5 ans.'),
  ('DREES_ASPA', 'MIN_VIEILLESSE', 'Allocataires du minimum vieillesse',
   'Allocataires de l''allocation de solidarité aux personnes âgées (ASPA) ou de '
   'l''allocation supplémentaire vieillesse (ASV), au 31 décembre.',
   'personnes', 'effectif', NULL,
   'Rhône : la Métropole de Lyon n''est pas distinguée.',
   'Comparable dans le temps et entre départements.'),
  ('DREES_ASPA', 'TAUX_MIN_VIEILLESSE_60P', 'Taux d''allocataires du minimum vieillesse',
   'Allocataires de l''ASPA ou de l''ASV pour 100 personnes de 60 ans ou plus.',
   'pourcentage', 'taux', '100 × allocataires / population de 60 ans ou plus',
   NULL,
   'Comparable dans le temps et entre départements.')
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement,
        comparabilite)
  ON v.source = s.code;

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
WHERE p.sexe = 'T' AND p.age_min IS NULL AND p.age_max IS NULL AND p.modalite_id IS NULL;
