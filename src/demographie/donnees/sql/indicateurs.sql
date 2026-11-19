SELECT code, libelle, definition, unite, nature, formule, avertissement, comparabilite,
       source_code, source_libelle, source_url, source_licence, mis_a_jour_le
FROM api.indicateur
WHERE %(code)s::text IS NULL OR code = %(code)s::text
ORDER BY array_position(
  ARRAY['POP', 'PART_MOINS_20', 'PART_60_PLUS', 'PART_75_PLUS', 'INDICE_VIEILLISSEMENT',
        'NAISSANCES', 'DECES', 'SOLDE_NATUREL', 'TAUX_NATALITE', 'TAUX_MORTALITE', 'ICF',
        'ESPERANCE_VIE'], code
), code
