SELECT t.code, t.niveau, t.libelle, t.parent_niveau, t.parent_code, p.libelle AS parent_libelle
FROM api.territoire t
LEFT JOIN api.territoire p ON (p.niveau, p.code) = (t.parent_niveau, t.parent_code)
WHERE t.niveau = %(niveau)s AND t.code = %(code)s
