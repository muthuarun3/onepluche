-- Rôles PostgreSQL de l'application.
-- À exécuter une fois par un superutilisateur (installation, intégration continue).
-- Idempotent : peut être relancé sans erreur.
-- Les mots de passe sont définis à part (deploy/installer.sh), jamais ici.

DO $$
BEGIN
  -- Propriétaire des schémas : utilisé uniquement pour les migrations.
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'demo_proprietaire') THEN
    CREATE ROLE demo_proprietaire LOGIN;
  END IF;
  -- Imports : écrit dans ingest et stat, lit ref.
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'demo_import') THEN
    CREATE ROLE demo_import LOGIN;
  END IF;
  -- Application : lecture seule sur le schéma api.
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'demo_lecture') THEN
    CREATE ROLE demo_lecture LOGIN;
  END IF;
END
$$;

-- Garde-fous appliqués par la base elle-même, quel que soit le code appelant.
ALTER ROLE demo_lecture SET statement_timeout = '5s';
ALTER ROLE demo_lecture SET default_transaction_read_only = on;
ALTER ROLE demo_import SET statement_timeout = '10min';
