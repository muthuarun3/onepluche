-- Les révisions du producteur remplacent les valeurs précédentes (le fichier brut
-- de chaque import reste archivé).
INSERT INTO stat.observation (indicateur_id, territoire_id, periode, periode_type, sexe,
                              age_min, age_max, modalite_id, valeur, statut, import_id)
SELECT indicateur_id, territoire_id, periode, periode_type, sexe,
       age_min, age_max, modalite_id, valeur, statut, import_id
FROM ingest.ligne
WHERE import_id = %(import_id)s AND a_publier
ON CONFLICT (indicateur_id, territoire_id, periode, sexe, age_min, age_max, modalite_id)
DO UPDATE SET periode_type = EXCLUDED.periode_type,
              valeur       = EXCLUDED.valeur,
              statut       = EXCLUDED.statut,
              import_id    = EXCLUDED.import_id
