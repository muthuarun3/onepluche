SELECT modalite, libelle, age_min, age_max, annee, periode_type, valeur, total, provisoire
FROM api.repartition r
WHERE indicateur = %(indicateur)s
  AND niveau = %(niveau)s
  AND code = %(code)s
  AND annee = coalesce(
    %(annee)s::int,
    (SELECT max(annee) FROM api.repartition
     WHERE indicateur = %(indicateur)s AND niveau = %(niveau)s AND code = %(code)s)
  )
ORDER BY age_min NULLS FIRST, age_max NULLS LAST, ordre
