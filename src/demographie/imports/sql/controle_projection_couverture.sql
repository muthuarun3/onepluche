-- Indicateurs et scénarios qui couvrent moins de départements qu'attendu.
SELECT i.code AS indicateur, sc.code AS scenario, count(DISTINCT l.territoire_id) AS departements
FROM ingest.ligne_projection l
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.scenario sc USING (scenario_id)
JOIN ref.territoire t USING (territoire_id)
WHERE l.import_id = %(import_id)s AND t.niveau = 'DEP'
GROUP BY i.code, sc.code
HAVING count(DISTINCT l.territoire_id) < %(attendus)s
ORDER BY i.code, sc.code
