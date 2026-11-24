-- Climat projeté d'un territoire : écart à 1995-2014 par indicateur, scénario et période,
-- médiane et fourchette des modèles.
SELECT c.indicateur, c.scenario, c.debut, c.fin, c.mediane, c.bas, c.haut
FROM api.projection_climat c
JOIN api.scenario s ON s.code = c.scenario
WHERE c.niveau = %(niveau)s AND c.code = %(code)s
ORDER BY s.ordre, c.indicateur, c.debut
