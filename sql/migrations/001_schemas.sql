-- Quatre schémas, quatre responsabilités (dossier de conception, étape 5).
CREATE SCHEMA ref;     -- référentiels : territoires, sources, indicateurs, modalités
CREATE SCHEMA ingest;  -- journal des imports et tables de transit
CREATE SCHEMA stat;    -- observations validées et vues dérivées
CREATE SCHEMA api;     -- vues stables exposées à l'application

-- Personne d'autre que le propriétaire ne crée d'objets dans public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
