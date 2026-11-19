-- Cohérence interne de chaque territoire : somme des tranches d'âge = total,
-- hommes + femmes = ensemble, pour les effectifs et les flux.
-- Renvoie les écarts au-delà de la tolérance.
WITH l AS (
  SELECT l.indicateur_id, l.territoire_id, l.periode, l.sexe, l.age_min, l.age_max, l.valeur
  FROM ingest.ligne l
  JOIN ref.indicateur i USING (indicateur_id)
  WHERE l.import_id = %(import_id)s AND l.modalite_id IS NULL
    AND i.nature IN ('effectif', 'flux')
),
tranches AS (
  SELECT indicateur_id, territoire_id, periode, sexe,
         sum(valeur) FILTER (WHERE age_min IS NOT NULL) AS somme,
         sum(valeur) FILTER (WHERE age_min IS NULL AND age_max IS NULL) AS total
  FROM l
  GROUP BY indicateur_id, territoire_id, periode, sexe
),
ecarts AS (
  SELECT indicateur_id, territoire_id, periode, sexe || ' : somme des âges' AS controle, total, somme
  FROM tranches
  WHERE somme IS NOT NULL AND total IS NOT NULL
  UNION ALL
  SELECT t.indicateur_id, t.territoire_id, t.periode, 'H + F' AS controle, t.total, h.total + f.total
  FROM tranches t
  JOIN tranches h ON (h.indicateur_id, h.territoire_id, h.periode, h.sexe)
                   = (t.indicateur_id, t.territoire_id, t.periode, 'H')
  JOIN tranches f ON (f.indicateur_id, f.territoire_id, f.periode, f.sexe)
                   = (t.indicateur_id, t.territoire_id, t.periode, 'F')
  WHERE t.sexe = 'T'
)
SELECT i.code AS indicateur, r.niveau, r.code, e.periode, e.controle, e.total AS publie,
       e.somme
FROM ecarts e
JOIN ref.territoire r USING (territoire_id)
JOIN ref.indicateur i USING (indicateur_id)
WHERE abs(e.total - e.somme) > %(tolerance)s * e.total
ORDER BY e.periode, r.niveau, r.code
