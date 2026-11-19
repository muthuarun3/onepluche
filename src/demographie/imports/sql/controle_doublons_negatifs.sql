SELECT
  (SELECT count(*) FROM ingest.ligne
   WHERE import_id = %(import_id)s AND valeur < 0) AS negatifs,
  (SELECT count(*) FROM (
     SELECT 1 FROM ingest.ligne
     WHERE import_id = %(import_id)s AND a_publier
     GROUP BY indicateur_id, territoire_id, periode, sexe, age_min, age_max, modalite_id
     HAVING count(*) > 1) d) AS doublons
