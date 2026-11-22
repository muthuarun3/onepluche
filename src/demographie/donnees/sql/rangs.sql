-- Pour chaque indicateur d'une rubrique publié par département : la valeur d'un
-- département à la dernière période départementale, son rang parmi les départements
-- (1 = la valeur la plus forte), le nombre de départements classés, et la valeur France
-- de la même période (France entière si publiée, sinon métropole).
WITH derniere AS (
  SELECT s.indicateur, max(s.periode) AS periode
  FROM api.serie s
  JOIN api.indicateur i ON i.code = s.indicateur
  WHERE i.rubrique = %(rubrique)s AND s.niveau = 'DEP' AND s.sexe = 'T'
  GROUP BY s.indicateur
), classes AS (
  SELECT s.indicateur, s.code, s.annee, s.periode, s.valeur, s.provisoire,
         rank() OVER (PARTITION BY s.indicateur ORDER BY s.valeur DESC) AS rang,
         count(*) OVER (PARTITION BY s.indicateur) AS classes
  FROM api.serie s
  JOIN derniere d ON d.indicateur = s.indicateur AND d.periode = s.periode
  WHERE s.niveau = 'DEP' AND s.sexe = 'T' AND s.valeur IS NOT NULL
)
SELECT c.indicateur, c.annee, c.valeur, c.provisoire, c.rang, c.classes,
       f.code AS france_code, f.valeur AS france_valeur, f.provisoire AS france_provisoire
FROM classes c
LEFT JOIN LATERAL (
  SELECT fr.code, fr.valeur, fr.provisoire
  FROM api.serie fr
  WHERE fr.indicateur = c.indicateur AND fr.niveau = 'FRANCE' AND fr.periode = c.periode
    AND fr.sexe = 'T'
  ORDER BY fr.code = 'FR' DESC
  LIMIT 1
) f ON true
WHERE c.code = %(code)s
ORDER BY c.indicateur
