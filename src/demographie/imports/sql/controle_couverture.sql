-- Départements manquants, pour chaque indicateur, à la période la plus récente du fichier.
-- Les départements absents de la source par construction (ex. Alsace-Moselle pour DVF)
-- sont exclus par le connecteur via %(absents)s.
WITH dernieres AS (
  SELECT indicateur_id, max(periode) AS periode
  FROM ingest.ligne
  WHERE import_id = %(import_id)s AND a_publier
  GROUP BY indicateur_id
),
presents AS (
  SELECT DISTINCT l.indicateur_id, l.territoire_id
  FROM ingest.ligne l
  JOIN dernieres d USING (indicateur_id, periode)
  WHERE l.import_id = %(import_id)s AND l.a_publier
)
SELECT i.code AS indicateur, d.periode,
       array_agg(t.code ORDER BY t.code) AS manquants
FROM dernieres d
JOIN ref.indicateur i USING (indicateur_id)
CROSS JOIN ref.territoire t
WHERE t.niveau = 'DEP'
  AND t.code <> ALL (%(absents)s::text[])
  AND NOT EXISTS (
    SELECT 1 FROM presents p
    WHERE p.indicateur_id = d.indicateur_id AND p.territoire_id = t.territoire_id
  )
GROUP BY i.code, d.periode
ORDER BY i.code
