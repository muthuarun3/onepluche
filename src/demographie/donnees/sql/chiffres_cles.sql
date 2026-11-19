-- Dernière année disponible de chaque indicateur pour un territoire.
SELECT DISTINCT ON (indicateur) indicateur, annee, valeur, provisoire
FROM api.serie
WHERE niveau = %(niveau)s AND code = %(code)s
ORDER BY indicateur, annee DESC
