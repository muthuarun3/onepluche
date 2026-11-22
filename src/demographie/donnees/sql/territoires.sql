SELECT code, niveau, libelle, parent_niveau, parent_code, cog_millesime
FROM api.territoire
WHERE %(niveau)s::text IS NULL OR niveau = %(niveau)s::text
ORDER BY array_position(ARRAY['FRANCE', 'REG', 'DEP', 'HORS_DEP'], niveau), code = 'FR' DESC, code
