SELECT annee, sexe, age_min, age_max, valeur, provisoire
FROM api.structure
WHERE niveau = %(niveau)s
  AND code = %(code)s
  AND annee = coalesce(
    %(annee)s::int,
    (SELECT max(annee) FROM api.structure WHERE niveau = %(niveau)s AND code = %(code)s)
  )
ORDER BY sexe, age_min
