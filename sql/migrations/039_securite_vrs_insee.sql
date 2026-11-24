-- Appli « Les Français sont-ils en sécurité ? » : l'enquête VRS n'est plus recopiée à la
-- main (fichier imports/fichiers/vrs.csv supprimé). Ses parts nationales sont lues
-- chaque année dans le tableur de la fiche « Insécurité, victimation » de l'Insee
-- (France, portrait social, publiée en novembre), trouvée par le moteur de recherche de
-- l'Insee.
UPDATE ref.source
SET producteur = 'Ministère de l''Intérieur (SSMSI), diffusé par l''Insee',
    libelle = 'Enquête Vécu et ressenti en matière de sécurité, fiche « Insécurité, victimation » de France, portrait social',
    url = 'https://www.insee.fr/fr/statistiques/8612552'
WHERE code = 'SSMSI_VRS';
