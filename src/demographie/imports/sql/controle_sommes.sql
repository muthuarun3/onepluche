-- France et France métropolitaine comparées à la somme des territoires les plus fins
-- du même fichier (tous âges, par indicateur et par sexe), pour les effectifs et les
-- flux seulement : un taux ne s'additionne pas. Renvoie les écarts au-delà de la tolérance.
WITH l AS (
  SELECT l.indicateur_id, l.periode, l.sexe, l.valeur, t.niveau, t.code,
         CASE WHEN t.niveau = 'DEP' THEN p.code ELSE t.code END AS region
  FROM ingest.ligne l
  JOIN ref.indicateur i USING (indicateur_id)
  JOIN ref.territoire t USING (territoire_id)
  LEFT JOIN ref.territoire p ON p.territoire_id = t.parent_id
  WHERE l.import_id = %(import_id)s
    AND l.age_min IS NULL AND l.age_max IS NULL
    AND i.nature IN ('effectif', 'flux')
),
plus_fin AS (
  SELECT indicateur_id,
         CASE WHEN bool_or(niveau = 'DEP') THEN 'DEP' ELSE 'REG' END AS niveau
  FROM l
  GROUP BY indicateur_id
),
sommes AS (
  SELECT l.indicateur_id, l.periode, l.sexe,
         sum(l.valeur) AS fr,
         sum(l.valeur) FILTER (WHERE l.region NOT IN ('01', '02', '03', '04', '06')) AS fm
  FROM l
  JOIN plus_fin f ON f.indicateur_id = l.indicateur_id AND f.niveau = l.niveau
  GROUP BY l.indicateur_id, l.periode, l.sexe
)
SELECT i.code AS indicateur, a.code, a.periode, a.sexe, a.valeur AS publie,
       CASE a.code WHEN 'FR' THEN s.fr ELSE s.fm END AS somme
FROM l a
JOIN sommes s USING (indicateur_id, periode, sexe)
JOIN ref.indicateur i USING (indicateur_id)
WHERE a.niveau = 'FRANCE'
  AND abs(a.valeur - coalesce(CASE a.code WHEN 'FR' THEN s.fr ELSE s.fm END, 0))
      > %(tolerance)s * a.valeur
ORDER BY a.periode, i.code, a.code, a.sexe
