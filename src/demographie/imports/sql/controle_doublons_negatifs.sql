SELECT
  -- Négatif interdit, sauf pour un indicateur dont la borne basse l'admet (solde public).
  (SELECT count(*) FROM ingest.ligne l JOIN ref.indicateur i USING (indicateur_id)
   WHERE l.import_id = %(import_id)s AND l.valeur < least(coalesce(i.borne_min, 0), 0))
     AS negatifs,
  (SELECT count(*) FROM ingest.ligne l JOIN ref.indicateur i USING (indicateur_id)
   WHERE l.import_id = %(import_id)s
     -- Plus de 100 pour cent seulement si la borne haute l'admet (dette en part du PIB).
     AND ((i.unite = 'pourcentage' AND l.valeur > greatest(coalesce(i.borne_max, 100), 100))
          OR (i.unite = 'pour_mille' AND l.valeur > 1000))) AS hors_bornes,
  (SELECT count(*) FROM (
     SELECT 1 FROM ingest.ligne
     WHERE import_id = %(import_id)s AND a_publier
     GROUP BY indicateur_id, territoire_id, periode, sexe, age_min, age_max, modalite_id
     HAVING count(*) > 1) d) AS doublons
