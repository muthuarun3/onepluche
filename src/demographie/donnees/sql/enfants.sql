SELECT code, niveau, libelle
FROM api.territoire
WHERE parent_niveau = %(niveau)s AND parent_code = %(code)s
ORDER BY code
