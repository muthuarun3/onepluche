-- Valeur par modalité d'un indicateur mensuel, au mois demandé.
SELECT modalite, libelle, periode, valeur, provisoire
FROM api.repartition_mensuelle
WHERE indicateur = %(indicateur)s
  AND niveau = %(niveau)s
  AND code = %(code)s
  AND periode = %(periode)s
ORDER BY ordre
