-- Valeurs projetées d'un indicateur pour un territoire (tous scénarios, ou un seul).
SELECT p.scenario, p.annee, p.periode, p.periode_fin, p.sexe, p.age_min, p.age_max,
       p.statistique, p.valeur
FROM api.projection p
JOIN api.scenario s ON s.code = p.scenario
WHERE p.indicateur = %(indicateur)s
  AND p.niveau = %(niveau)s AND p.code = %(code)s
  AND (%(scenario)s::text IS NULL OR p.scenario = %(scenario)s::text)
  AND p.sexe = %(sexe)s
  AND (%(par_age)s OR (p.age_min IS NULL AND p.age_max IS NULL))
ORDER BY s.ordre, p.periode, p.age_min NULLS FIRST, p.statistique
