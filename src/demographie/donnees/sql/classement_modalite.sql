-- Comme classement.sql, pour une modalité (famille de métiers…) : valeur de chaque
-- département à la dernière période départementale, et valeur France (France entière si
-- publiée, sinon métropole). Les départements sans valeur sont rendus avec NULL.
WITH periode AS (
  SELECT max(v.periode) AS periode
  FROM api.ventilation v
  WHERE v.indicateur = %(indicateur)s AND v.niveau = 'DEP' AND v.sexe = 'T'
    AND v.dimension = %(dimension)s AND v.modalite = %(modalite)s
)
SELECT t.code, t.libelle, t.parent_code AS region,
       extract(year FROM p.periode)::int AS annee, v.valeur, v.provisoire,
       f.code AS france_code, f.valeur AS france_valeur, f.provisoire AS france_provisoire
FROM periode p
CROSS JOIN api.territoire t
LEFT JOIN api.ventilation v
  ON v.indicateur = %(indicateur)s AND v.niveau = 'DEP' AND v.code = t.code
 AND v.periode = p.periode AND v.sexe = 'T' AND v.age_min IS NULL
 AND v.dimension = %(dimension)s AND v.modalite = %(modalite)s
LEFT JOIN LATERAL (
  SELECT fr.code, fr.valeur, fr.provisoire
  FROM api.ventilation fr
  WHERE fr.indicateur = %(indicateur)s AND fr.niveau = 'FRANCE' AND fr.periode = p.periode
    AND fr.sexe = 'T' AND fr.age_min IS NULL
    AND fr.dimension = %(dimension)s AND fr.modalite = %(modalite)s
  ORDER BY fr.code = 'FR' DESC
  LIMIT 1
) f ON true
WHERE t.niveau = 'DEP' AND p.periode IS NOT NULL
ORDER BY v.valeur DESC NULLS LAST, t.code
