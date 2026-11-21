-- Dernière année de chaque indicateur demandé, par tranche d'âge, pour un territoire,
-- avec la valeur France de la même période (France entière, sinon métropole).
WITH derniere AS (
  SELECT DISTINCT ON (a.indicateur, a.age_min, a.age_max)
         a.indicateur, a.age_min, a.age_max, a.annee, a.periode, a.valeur, a.provisoire
  FROM api.serie_age a
  WHERE a.niveau = %(niveau)s AND a.code = %(code)s
    AND a.indicateur = ANY(%(indicateurs)s::text[])
  ORDER BY a.indicateur, a.age_min, a.age_max, a.periode DESC
)
SELECT d.*, f.code AS france_code, f.valeur AS france_valeur
FROM derniere d
LEFT JOIN LATERAL (
  SELECT a.code, a.valeur
  FROM api.serie_age a
  WHERE a.indicateur = d.indicateur AND a.niveau = 'FRANCE' AND a.periode = d.periode
    AND a.age_min IS NOT DISTINCT FROM d.age_min AND a.age_max IS NOT DISTINCT FROM d.age_max
  ORDER BY a.code = 'FR' DESC
  LIMIT 1
) f ON true
ORDER BY d.age_min NULLS FIRST, d.indicateur
