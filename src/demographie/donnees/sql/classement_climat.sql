-- Climat projeté de chaque département (et de la France métropolitaine, code 'FM') pour
-- un indicateur, un scénario et une période : médiane et fourchette des modèles. Les
-- départements sans projection (outre-mer) sont rendus avec NULL.
SELECT t.niveau, t.code, t.libelle, c.mediane AS valeur, c.bas, c.haut
FROM api.territoire t
LEFT JOIN api.projection_climat c
  ON c.niveau = t.niveau AND c.code = t.code AND c.indicateur = %(indicateur)s
 AND c.scenario = %(scenario)s AND c.debut = %(debut)s
WHERE t.niveau = 'DEP' OR (t.niveau = 'FRANCE' AND t.code = 'FM')
ORDER BY t.niveau = 'DEP', t.code
