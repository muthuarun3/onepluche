-- Dernière valeur de chaque indicateur d'une rubrique (et d'un thème) pour un territoire,
-- avec la valeur France de la même période : France entière si publiée, sinon France
-- métropolitaine (Filosofi, par exemple, ne publie pas de total France entière).
WITH derniere AS (
  SELECT DISTINCT ON (s.indicateur)
         s.indicateur, s.annee, s.periode, s.periode_type, s.valeur, s.provisoire,
         coalesce(a.theme, i.theme) AS theme,
         CASE WHEN a.rubrique IS NULL THEN i.angle END AS angle
  FROM api.serie s
  JOIN api.indicateur i ON i.code = s.indicateur
  -- Indicateurs d'une autre rubrique affichés aussi dans celle-ci (migration 031).
  LEFT JOIN api.indicateur_affichage a
    ON a.indicateur = i.code AND a.rubrique = %(rubrique)s
  WHERE s.niveau = %(niveau)s AND s.code = %(code)s AND s.sexe = 'T'
    AND (i.rubrique = %(rubrique)s OR a.rubrique IS NOT NULL)
    AND (%(theme)s::text IS NULL OR coalesce(a.theme, i.theme) = %(theme)s::text)
  ORDER BY s.indicateur, s.periode DESC
)
SELECT d.indicateur, d.annee, d.periode, d.periode_type, d.valeur, d.provisoire,
       f.code AS france_code, f.valeur AS france_valeur, f.provisoire AS france_provisoire
FROM derniere d
LEFT JOIN LATERAL (
  SELECT s.code, s.valeur, s.provisoire
  FROM api.serie s
  WHERE s.indicateur = d.indicateur AND s.niveau = 'FRANCE' AND s.periode = d.periode
    AND s.sexe = 'T'
  ORDER BY s.code = 'FR' DESC
  LIMIT 1
) f ON true
ORDER BY d.theme NULLS FIRST,
         array_position(ARRAY['ACCES', 'COUT', 'MANQUE'], d.angle) NULLS LAST,
         d.indicateur
