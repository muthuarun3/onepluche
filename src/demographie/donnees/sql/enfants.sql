SELECT code, niveau, libelle
FROM api.territoire
-- Les territoires hors département (rubrique VOTES) ne sont pas des enfants affichés.
WHERE parent_niveau = %(niveau)s AND parent_code = %(code)s AND niveau <> 'HORS_DEP'
ORDER BY code
