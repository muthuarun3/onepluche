-- Définitions des indicateurs. Avec une rubrique : ses propres indicateurs et ceux d'autres
-- rubriques qu'elle affiche aussi (api.indicateur_affichage), sous le thème de la rubrique
-- demandée et sans angle de lecture.
SELECT i.code, i.libelle, i.definition, i.unite, i.nature, i.formule, i.avertissement,
       i.comparabilite, i.source_code, i.source_libelle, i.source_url, i.source_licence,
       i.mis_a_jour_le,
       coalesce(a.rubrique, i.rubrique) AS rubrique,
       coalesce(a.theme, i.theme) AS theme,
       CASE WHEN a.rubrique IS NULL THEN i.angle END AS angle
FROM api.indicateur i
LEFT JOIN api.indicateur_affichage a
  ON a.indicateur = i.code AND a.rubrique = %(rubrique)s::text
WHERE (%(code)s::text IS NULL OR i.code = %(code)s::text)
  AND (%(rubrique)s::text IS NULL OR i.rubrique = %(rubrique)s::text OR a.rubrique IS NOT NULL)
  AND (%(theme)s::text IS NULL OR coalesce(a.theme, i.theme) = %(theme)s::text)
ORDER BY array_position(
  ARRAY['POP', 'PART_MOINS_20', 'PART_60_PLUS', 'PART_75_PLUS', 'INDICE_VIEILLISSEMENT',
        'NAISSANCES', 'DECES', 'SOLDE_NATUREL', 'TAUX_NATALITE', 'TAUX_MORTALITE', 'ICF',
        'ESPERANCE_VIE'], i.code
), a.ordre NULLS LAST, i.code
