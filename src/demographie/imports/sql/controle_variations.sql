-- Valeurs déjà publiées qui changeraient de plus que le seuil : l'import attend alors
-- une validation humaine (révision exceptionnelle ou erreur de lecture ?).
-- Règle générale : les totaux des effectifs, au seuil %(seuil)s ; les flux et les taux des
-- petits territoires bougent plus. Un indicateur qui déclare son propre seuil
-- (seuil_variation : prix, médianes) est contrôlé à ce seuil, modalités comprises.
SELECT t.niveau, t.code, l.periode, o.valeur AS ancienne, l.valeur AS nouvelle
FROM ingest.ligne l
JOIN ref.indicateur i ON i.indicateur_id = l.indicateur_id
JOIN stat.observation o
  ON o.indicateur_id = l.indicateur_id
 AND o.territoire_id = l.territoire_id
 AND o.periode = l.periode
 AND o.sexe = l.sexe
 AND o.age_min IS NOT DISTINCT FROM l.age_min
 AND o.age_max IS NOT DISTINCT FROM l.age_max
 AND o.modalite_id IS NOT DISTINCT FROM l.modalite_id
JOIN ref.territoire t ON t.territoire_id = l.territoire_id
WHERE l.import_id = %(import_id)s
  AND l.a_publier
  AND l.sexe = 'T' AND l.age_min IS NULL AND l.age_max IS NULL
  AND (
    (i.seuil_variation IS NULL AND i.nature = 'effectif' AND l.modalite_id IS NULL
     AND abs(l.valeur - o.valeur) > %(seuil)s * o.valeur)
    OR (i.seuil_variation IS NOT NULL
        AND abs(l.valeur - o.valeur) > i.seuil_variation * o.valeur)
  )
ORDER BY abs(l.valeur - o.valeur) / nullif(o.valeur, 0) DESC NULLS LAST
LIMIT 20
