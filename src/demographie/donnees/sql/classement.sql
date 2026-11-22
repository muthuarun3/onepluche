-- Valeur d'un indicateur pour chaque département, à la dernière période publiée au
-- niveau départemental, avec la valeur France de la même période (France entière si
-- publiée, sinon métropole). Les départements sans valeur sont rendus avec NULL.
WITH periode AS (
  SELECT max(s.periode) AS periode
  FROM api.serie s
  WHERE s.indicateur = %(indicateur)s AND s.niveau = 'DEP' AND s.sexe = 'T'
)
SELECT t.code, t.libelle, t.parent_code AS region,
       extract(year FROM p.periode)::int AS annee, s.valeur, s.provisoire,
       f.code AS france_code, f.valeur AS france_valeur, f.provisoire AS france_provisoire
FROM periode p
CROSS JOIN api.territoire t
LEFT JOIN api.serie s
  ON s.indicateur = %(indicateur)s AND s.niveau = 'DEP' AND s.code = t.code
 AND s.periode = p.periode AND s.sexe = 'T'
LEFT JOIN LATERAL (
  SELECT fr.code, fr.valeur, fr.provisoire
  FROM api.serie fr
  WHERE fr.indicateur = %(indicateur)s AND fr.niveau = 'FRANCE' AND fr.periode = p.periode
    AND fr.sexe = 'T'
  ORDER BY fr.code = 'FR' DESC
  LIMIT 1
) f ON true
WHERE t.niveau = 'DEP' AND p.periode IS NOT NULL
ORDER BY s.valeur DESC NULLS LAST, t.code
