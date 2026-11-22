-- Population projetée par sexe et tranche d'âge (Omphale), pour les années demandées,
-- dans un scénario.
SELECT annee, sexe, age_min, age_max, valeur
FROM api.projection
WHERE indicateur = 'PROJ_POP'
  AND niveau = %(niveau)s AND code = %(code)s
  AND scenario = %(scenario)s
  AND annee = ANY(%(annees)s::int[])
  AND sexe IN ('H', 'F') AND age_min IS NOT NULL
ORDER BY annee, age_min, sexe
