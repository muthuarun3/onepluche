-- Somme d'un indicateur (total, sans ventilation) de l'année %(debut)s à %(fin)s pour
-- chaque département et pour la France entière (code 'FR').
SELECT t.niveau, t.code, t.libelle, sum(s.valeur) AS valeur
FROM api.territoire t
LEFT JOIN api.serie s
  ON s.niveau = t.niveau AND s.code = t.code AND s.indicateur = %(indicateur)s
 AND s.sexe = 'T' AND s.annee BETWEEN %(debut)s AND %(fin)s
WHERE t.niveau = 'DEP' OR (t.niveau = 'FRANCE' AND t.code = 'FR')
GROUP BY t.niveau, t.code, t.libelle
ORDER BY t.niveau = 'DEP', t.code
