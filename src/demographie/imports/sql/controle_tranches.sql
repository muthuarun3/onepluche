-- Cohérence interne de chaque territoire : somme des tranches d'âge = total,
-- hommes + femmes = ensemble. Renvoie les écarts au-delà de la tolérance.
WITH l AS (
  SELECT l.territoire_id, l.periode, l.sexe, l.age_min, l.age_max, l.valeur
  FROM ingest.ligne l
  WHERE l.import_id = %(import_id)s AND l.modalite_id IS NULL
),
tranches AS (
  SELECT territoire_id, periode, sexe,
         sum(valeur) FILTER (WHERE age_min IS NOT NULL) AS somme,
         sum(valeur) FILTER (WHERE age_min IS NULL AND age_max IS NULL) AS total
  FROM l
  GROUP BY territoire_id, periode, sexe
),
ecarts AS (
  SELECT territoire_id, periode, sexe || ' : somme des âges' AS controle, total, somme
  FROM tranches
  WHERE somme IS NOT NULL AND total IS NOT NULL
  UNION ALL
  SELECT t.territoire_id, t.periode, 'H + F' AS controle, t.total, h.total + f.total
  FROM tranches t
  JOIN tranches h ON (h.territoire_id, h.periode, h.sexe) = (t.territoire_id, t.periode, 'H')
  JOIN tranches f ON (f.territoire_id, f.periode, f.sexe) = (t.territoire_id, t.periode, 'F')
  WHERE t.sexe = 'T'
)
SELECT r.niveau, r.code, e.periode, e.controle, e.total AS publie, e.somme
FROM ecarts e
JOIN ref.territoire r USING (territoire_id)
WHERE abs(e.total - e.somme) > %(tolerance)s * e.total
ORDER BY e.periode, r.niveau, r.code
