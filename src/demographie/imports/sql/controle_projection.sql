-- Contrôles d'un fichier de projections : doublons, valeurs hors des bornes du catalogue
-- (négatives comprises, sauf pour les flux qui déclarent une borne basse négative) et
-- fourchette incohérente (bas > médiane ou médiane > haut).
SELECT
  (SELECT count(*) FROM (
     SELECT 1 FROM ingest.ligne_projection
     WHERE import_id = %(import_id)s
     GROUP BY indicateur_id, territoire_id, scenario_id, periode, periode_fin, sexe,
              age_min, age_max, statistique
     HAVING count(*) > 1) d) AS doublons,
  (SELECT count(*) FROM ingest.ligne_projection l JOIN ref.indicateur i USING (indicateur_id)
   WHERE l.import_id = %(import_id)s
     AND ((l.valeur < coalesce(i.borne_min, 0))
          OR (i.borne_max IS NOT NULL AND l.valeur > i.borne_max)
          OR (i.unite = 'pourcentage' AND l.valeur > 100))) AS hors_bornes,
  (SELECT count(*) FROM (
     SELECT 1 FROM ingest.ligne_projection
     WHERE import_id = %(import_id)s AND statistique IN ('BAS', 'MEDIANE', 'HAUT')
     GROUP BY indicateur_id, territoire_id, scenario_id, periode, periode_fin, sexe,
              age_min, age_max
     HAVING max(valeur) FILTER (WHERE statistique = 'BAS')
              > min(valeur) FILTER (WHERE statistique = 'MEDIANE')
         OR max(valeur) FILTER (WHERE statistique = 'MEDIANE')
              > min(valeur) FILTER (WHERE statistique = 'HAUT')) f) AS fourchettes
