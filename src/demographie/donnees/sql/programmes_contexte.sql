-- Contexte chiffré des pages « Programmes » : pour chaque indicateur cité, sa définition,
-- sa source, l'appli de « Données » qui le présente et sa dernière valeur pour la France.
SELECT i.code, i.libelle, i.definition, i.unite, i.source_libelle, i.source_url,
       r.libelle AS rubrique_libelle, r.chemin AS rubrique_chemin,
       s.annee, s.periode, s.periode_type, s.valeur, s.provisoire
FROM api.indicateur i
LEFT JOIN api.rubrique r ON r.code = i.rubrique
LEFT JOIN LATERAL (
  SELECT annee, periode, periode_type, valeur, provisoire
  FROM api.serie
  WHERE indicateur = i.code AND niveau = 'FRANCE' AND code = 'FR' AND sexe = 'T'
  ORDER BY periode DESC
  LIMIT 1
) s ON true
WHERE i.code = ANY(%(codes)s)
