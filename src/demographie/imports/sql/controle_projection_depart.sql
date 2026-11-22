-- Point de départ d'une projection de population : à la première année projetée, la
-- population totale de chaque territoire doit être à moins de %(tolerance)s des
-- estimations INSEE déjà publiées pour la même date (POP au 1er janvier).
SELECT t.niveau, t.code, l.periode, o.valeur AS estimation, l.valeur AS projection
FROM ingest.ligne_projection l
JOIN ref.indicateur i ON i.indicateur_id = l.indicateur_id AND i.code = 'PROJ_POP'
JOIN ref.indicateur pop ON pop.code = 'POP'
JOIN stat.observation o
  ON o.indicateur_id = pop.indicateur_id
 AND o.territoire_id = l.territoire_id
 AND o.periode = l.periode
 AND o.sexe = 'T' AND o.age_min IS NULL AND o.age_max IS NULL AND o.modalite_id IS NULL
JOIN ref.territoire t ON t.territoire_id = l.territoire_id
WHERE l.import_id = %(import_id)s
  AND l.sexe = 'T' AND l.age_min IS NULL AND l.age_max IS NULL
  AND l.periode = (SELECT min(periode) FROM ingest.ligne_projection
                   WHERE import_id = %(import_id)s)
  AND abs(l.valeur - o.valeur) > %(tolerance)s * o.valeur
ORDER BY abs(l.valeur - o.valeur) / o.valeur DESC
LIMIT 20
