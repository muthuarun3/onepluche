SELECT annee, periode, periode_type, valeur, provisoire
FROM api.serie
WHERE indicateur = %(indicateur)s
  AND niveau = %(niveau)s
  AND code = %(code)s
  AND sexe = %(sexe)s
  AND (%(debut)s::int IS NULL OR annee >= %(debut)s::int)
  AND (%(fin)s::int IS NULL OR annee <= %(fin)s::int)
ORDER BY periode
