-- Population projetée (Omphale) de chaque département pour un scénario et une année, avec
-- son évolution depuis l'année de départ ; la France (somme des départements) en tête,
-- code 'FR'. Les départements sans projection sont rendus avec NULL.
SELECT t.niveau, t.code, t.libelle, p.population, p.part_75_plus, p.seniors_pour_100_actifs,
       round(100 * (p.population - d.population) / nullif(d.population, 0), 2) AS evolution
FROM api.territoire t
LEFT JOIN api.projection_population p
  ON p.niveau = t.niveau AND p.code = t.code AND p.scenario = %(scenario)s
 AND p.annee = %(annee)s
LEFT JOIN api.projection_population d
  ON d.niveau = t.niveau AND d.code = t.code AND d.scenario = %(scenario)s
 AND d.annee = %(depart)s
WHERE t.niveau = 'DEP' OR (t.niveau = 'FRANCE' AND t.code = 'FR')
ORDER BY t.niveau = 'DEP', t.code
