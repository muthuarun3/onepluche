-- Une nouvelle édition remplace toute la projection d'un indicateur dans un scénario
-- (le fichier brut de chaque import reste archivé).
DELETE FROM stat.projection p
USING (SELECT DISTINCT indicateur_id, scenario_id FROM ingest.ligne_projection
       WHERE import_id = %(import_id)s) n
WHERE p.indicateur_id = n.indicateur_id AND p.scenario_id = n.scenario_id
