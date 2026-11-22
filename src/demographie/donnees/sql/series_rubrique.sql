-- Toutes les valeurs annuelles des indicateurs d'une rubrique pour un territoire (tous
-- sexes), par indicateur puis par période.
SELECT s.indicateur, s.annee, s.periode, s.valeur, s.provisoire
FROM api.serie s
JOIN api.indicateur i ON i.code = s.indicateur
WHERE i.rubrique = %(rubrique)s AND s.niveau = %(niveau)s AND s.code = %(code)s
  AND s.sexe = 'T' AND s.periode_type = 'ANNEE'
ORDER BY s.indicateur, s.periode
