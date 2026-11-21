-- Valeurs hors des bornes plausibles déclarées dans le catalogue (borne_min, borne_max).
-- Une seule valeur hors bornes fait rejeter l'import : erreur de lecture probable
-- (unité, séparateur décimal, colonne décalée).
SELECT i.code AS indicateur, t.niveau, t.code, l.periode, l.valeur,
       i.borne_min, i.borne_max
FROM ingest.ligne l
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
WHERE l.import_id = %(import_id)s
  AND ((i.borne_min IS NOT NULL AND l.valeur < i.borne_min)
       OR (i.borne_max IS NOT NULL AND l.valeur > i.borne_max))
ORDER BY i.code, t.niveau, t.code, l.periode
LIMIT 20
