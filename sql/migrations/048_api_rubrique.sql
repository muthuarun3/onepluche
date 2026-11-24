-- Programmes, P3 : les pages des programmes relient chaque chiffre de contexte à l'appli
-- de « Données » qui le présente. Le rôle lecture ne voit que le schéma api.
CREATE VIEW api.rubrique AS
SELECT code, libelle, chemin, ordre
FROM ref.rubrique;

GRANT SELECT ON api.rubrique TO demo_lecture;
