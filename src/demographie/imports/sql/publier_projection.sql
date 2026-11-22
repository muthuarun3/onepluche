INSERT INTO stat.projection (indicateur_id, territoire_id, scenario_id, periode, periode_fin,
                             sexe, age_min, age_max, statistique, valeur, import_id)
SELECT indicateur_id, territoire_id, scenario_id, periode, periode_fin,
       sexe, age_min, age_max, statistique, valeur, import_id
FROM ingest.ligne_projection
WHERE import_id = %(import_id)s
