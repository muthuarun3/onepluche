-- Totaux déjà publiés qui changeraient de plus que le seuil (nouvelle édition des
-- projections, ou erreur de lecture) : l'import attend une validation humaine.
SELECT t.niveau, t.code, sc.code AS scenario, l.periode, p.valeur AS ancienne,
       l.valeur AS nouvelle
FROM ingest.ligne_projection l
JOIN ref.indicateur i ON i.indicateur_id = l.indicateur_id
JOIN stat.projection p
  ON p.indicateur_id = l.indicateur_id
 AND p.territoire_id = l.territoire_id
 AND p.scenario_id = l.scenario_id
 AND p.periode = l.periode
 AND p.periode_fin IS NOT DISTINCT FROM l.periode_fin
 AND p.sexe = l.sexe
 AND p.age_min IS NOT DISTINCT FROM l.age_min
 AND p.age_max IS NOT DISTINCT FROM l.age_max
 AND p.statistique = l.statistique
JOIN ref.territoire t ON t.territoire_id = l.territoire_id
JOIN ref.scenario sc ON sc.scenario_id = l.scenario_id
WHERE l.import_id = %(import_id)s
  AND l.sexe = 'T' AND l.age_min IS NULL AND l.age_max IS NULL
  AND abs(l.valeur - p.valeur) > coalesce(i.seuil_variation, %(seuil)s) * abs(p.valeur)
ORDER BY abs(l.valeur - p.valeur) / nullif(abs(p.valeur), 0) DESC NULLS LAST
LIMIT 20
