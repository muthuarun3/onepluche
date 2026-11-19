-- Totaux déjà publiés qui changeraient de plus que le seuil : l'import attend alors
-- une validation humaine (révision exceptionnelle ou erreur de lecture ?).
SELECT t.niveau, t.code, l.periode, o.valeur AS ancienne, l.valeur AS nouvelle
FROM ingest.ligne l
JOIN stat.observation o
  ON o.indicateur_id = l.indicateur_id
 AND o.territoire_id = l.territoire_id
 AND o.periode = l.periode
 AND o.sexe = l.sexe
 AND o.age_min IS NULL AND o.age_max IS NULL AND o.modalite_id IS NULL
JOIN ref.territoire t ON t.territoire_id = l.territoire_id
WHERE l.import_id = %(import_id)s
  AND l.a_publier
  AND l.sexe = 'T' AND l.age_min IS NULL AND l.age_max IS NULL
  AND abs(l.valeur - o.valeur) > %(seuil)s * o.valeur
ORDER BY abs(l.valeur - o.valeur) / o.valeur DESC
LIMIT 20
