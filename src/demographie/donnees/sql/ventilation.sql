-- Valeurs ventilées d'un indicateur pour un territoire (par sexe, âge ou modalité d'une
-- dimension), toutes périodes, par période croissante.
SELECT periode, periode_type, annee, sexe, age_min, age_max, dimension, modalite, libelle,
       valeur, provisoire
FROM api.ventilation
WHERE indicateur = %(indicateur)s
  AND niveau = %(niveau)s
  AND code = %(code)s
  AND (%(dimension)s::text IS NULL OR dimension = %(dimension)s::text)
  AND (%(debut)s::int IS NULL OR annee >= %(debut)s::int)
ORDER BY periode, modalite, sexe, age_min NULLS FIRST
