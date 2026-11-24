SELECT election, candidat, version, url, releve_le, statut_http, sha256, change, message,
       dernier_changement
FROM api.programme_releve
ORDER BY election DESC, candidat, version
