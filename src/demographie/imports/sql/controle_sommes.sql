-- France et France métropolitaine comparées à la somme des territoires les plus fins
-- du même fichier (tous âges, par sexe). Renvoie les écarts au-delà de la tolérance.
WITH l AS (
  SELECT l.periode, l.sexe, l.valeur, t.niveau, t.code,
         CASE WHEN t.niveau = 'DEP' THEN p.code ELSE t.code END AS region
  FROM ingest.ligne l
  JOIN ref.territoire t USING (territoire_id)
  LEFT JOIN ref.territoire p ON p.territoire_id = t.parent_id
  WHERE l.import_id = %(import_id)s AND l.age_min IS NULL AND l.age_max IS NULL
),
plus_fin AS (
  SELECT CASE WHEN bool_or(niveau = 'DEP') THEN 'DEP' ELSE 'REG' END AS niveau FROM l
),
sommes AS (
  SELECT periode, sexe,
         sum(valeur) AS fr,
         sum(valeur) FILTER (WHERE region NOT IN ('01', '02', '03', '04', '06')) AS fm
  FROM l
  WHERE niveau = (SELECT niveau FROM plus_fin)
  GROUP BY periode, sexe
)
SELECT a.code, a.periode, a.sexe, a.valeur AS publie,
       CASE a.code WHEN 'FR' THEN s.fr ELSE s.fm END AS somme
FROM l a
JOIN sommes s USING (periode, sexe)
WHERE a.niveau = 'FRANCE'
  AND abs(a.valeur - coalesce(CASE a.code WHEN 'FR' THEN s.fr ELSE s.fm END, 0))
      > %(tolerance)s * a.valeur
ORDER BY a.periode, a.code, a.sexe
