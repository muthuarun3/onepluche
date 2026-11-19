SELECT source, producteur, source_libelle, source_url, licence, fichier_nom,
       dernier_statut, dernier_essai, derniere_publication, millesime
FROM api.etat_import
ORDER BY source, fichier_nom
