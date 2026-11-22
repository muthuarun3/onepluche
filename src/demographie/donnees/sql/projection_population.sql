-- Population projetée d'un territoire (Omphale), par scénario et année : population,
-- parts des moins de 20 ans et des 75 ans ou plus, seniors pour 100 actifs.
SELECT p.scenario, s.libelle AS scenario_libelle, p.annee, p.population, p.part_moins_20,
       p.part_75_plus, p.seniors_pour_100_actifs
FROM api.projection_population p
JOIN api.scenario s ON s.code = p.scenario
WHERE p.niveau = %(niveau)s AND p.code = %(code)s
ORDER BY s.ordre, p.annee
