-- Vues stables lues par l'application. L'application n'a accès qu'à ce schéma.
CREATE VIEW api.territoire AS
SELECT t.code,
       t.niveau,
       t.libelle,
       p.niveau AS parent_niveau,
       p.code   AS parent_code,
       t.cog_millesime
FROM ref.territoire t
LEFT JOIN ref.territoire p ON p.territoire_id = t.parent_id;

CREATE VIEW api.source AS
SELECT code, producteur, libelle, url, licence
FROM ref.source;

-- Droits du rôle d'import : lit les référentiels, écrit le journal et les observations.
GRANT USAGE ON SCHEMA ref, ingest, stat TO demo_import;
GRANT SELECT ON ALL TABLES IN SCHEMA ref TO demo_import;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ingest, stat TO demo_import;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA ingest TO demo_import;

-- Droits du rôle de lecture : uniquement les vues du schéma api.
GRANT USAGE ON SCHEMA api TO demo_lecture;
GRANT SELECT ON ALL TABLES IN SCHEMA api TO demo_lecture;
