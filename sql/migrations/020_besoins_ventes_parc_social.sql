-- Appli 2, phase B : prix de vente des logements (DVF) et parc social (RPLS). Dossier
-- de conception de l'appli 2, étapes 5 et 6. Le connecteur DVF calcule la médiane du prix au m² par
-- département, région et France, selon les règles de l'étape 6 : ventes d'un seul
-- logement, surface d'au moins 9 m², prix d'au moins 1 000 €, 1 % des prix au m² exclus
-- de chaque côté, médiane publiée seulement à partir de 30 ventes.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('DGFIP_DVF', 'DGFiP (diffusion Etalab)',
   'Demandes de valeurs foncières (DVF) géolocalisées : ventes immobilières',
   'https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees/');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('type_logement', 'APPARTEMENT', 'Appartements'),
  ('type_logement', 'MAISON', 'Maisons');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, NULL, 'BESOINS', 'LOGEMENT', 'COUT',
       v.borne_min, v.borne_max, v.seuil_variation
FROM (VALUES
  ('PRIX_VENTE_M2', 'Prix de vente médian au m²',
   'Prix médian au m² de surface habitable des logements vendus dans l''année (ventes '
   'd''un seul appartement ou d''une seule maison, dépendances comprises), selon les '
   'actes enregistrés par les services fiscaux.',
   'euros_m2', 'prix',
   'Médiane de valeur foncière / surface réelle bâtie, après exclusion du 1 % des prix '
   'au m² les plus bas et du 1 % les plus hauts ; publiée à partir de 30 ventes',
   'Hors Alsace-Moselle et Mayotte, absentes de DVF (livre foncier local). La dernière '
   'année est provisoire tant qu''elle n''est pas complète.',
   300, 25000, 0.15),
  ('ANNEES_REVENU_60M2', 'Années de niveau de vie pour 60 m²',
   'Nombre d''années de niveau de vie médian qu''il faudrait pour payer un logement '
   'de 60 m² au prix médian du territoire.',
   'annees', 'ratio',
   '60 × prix de vente médian au m² / niveau de vie médian annuel (Filosofi, dernière '
   'année disponible jusqu''à celle de la vente)',
   'Ordre de grandeur, sans apport ni crédit. Le niveau de vie est un revenu par unité '
   'de consommation après impôts et prestations, pas un salaire.',
   0, 100, NULL)
) AS v (code, libelle, definition, unite, nature, formule, avertissement, borne_min,
        borne_max, seuil_variation)
CROSS JOIN ref.source s
WHERE s.code = 'DGFIP_DVF';

-- Les indicateurs calculés de l'appli 2 gagnent le nombre d'années de revenu.
CREATE OR REPLACE VIEW stat.besoins_derives AS
WITH part AS (
  -- Part d'une modalité dans le total de la même série (même indicateur, territoire,
  -- période, sans tranche d'âge).
  SELECT d.code AS indicateur, o.territoire_id, o.periode, o.periode_type,
         o.statut = 'PROVISOIRE' AS provisoire,
         round(100 * o.valeur / nullif(tot.valeur, 0), 1) AS valeur
  FROM (VALUES
    ('PART_PROPRIETAIRES', 'RESIDENCES_PRINC', 'statut_occupation', 'PROPRIETAIRE'),
    ('PART_LOCATAIRES_HLM', 'RESIDENCES_PRINC', 'statut_occupation', 'LOCATAIRE_HLM'),
    ('PART_LOGEMENTS_VACANTS', 'LOGEMENTS', 'categorie_logement', 'VACANT'),
    ('PART_CHAUFFAGE_FIOUL', 'RESIDENCES_PRINC_CHAUFFAGE', 'combustible', 'FIOUL')
  ) AS d (code, base, dimension, modalite)
  JOIN ref.indicateur i ON i.code = d.base
  JOIN ref.modalite m ON m.dimension = d.dimension AND m.code = d.modalite
  JOIN stat.observation o
    ON o.indicateur_id = i.indicateur_id AND o.modalite_id = m.modalite_id
   AND o.sexe = 'T' AND o.age_min IS NULL AND o.age_max IS NULL
  JOIN stat.observation tot
    ON tot.indicateur_id = o.indicateur_id AND tot.territoire_id = o.territoire_id
   AND tot.periode = o.periode AND tot.sexe = 'T'
   AND tot.age_min IS NULL AND tot.age_max IS NULL AND tot.modalite_id IS NULL
)
SELECT p.indicateur, t.niveau, t.code, extract(year FROM p.periode)::int AS annee,
       p.valeur, p.provisoire, 'T'::char(1) AS sexe, p.periode, p.periode_type
FROM part p
JOIN ref.territoire t USING (territoire_id)
WHERE p.valeur IS NOT NULL
UNION ALL
SELECT 'ANNEES_REVENU_60M2', t.niveau, t.code, extract(year FROM p.periode)::int,
       round(60 * p.valeur / nullif(r.valeur, 0), 1), p.statut = 'PROVISOIRE',
       'T'::char(1), p.periode, p.periode_type
FROM stat.observation p
JOIN ref.indicateur pi ON pi.indicateur_id = p.indicateur_id AND pi.code = 'PRIX_VENTE_M2'
JOIN ref.territoire t ON t.territoire_id = p.territoire_id
CROSS JOIN LATERAL (
  SELECT o.valeur
  FROM stat.observation o
  JOIN ref.indicateur ri ON ri.indicateur_id = o.indicateur_id
  WHERE ri.code = 'NIVEAU_VIE_MEDIAN' AND o.territoire_id = p.territoire_id
    AND o.periode <= p.periode AND o.sexe = 'T' AND o.modalite_id IS NULL
    AND o.age_min IS NULL AND o.age_max IS NULL
  ORDER BY o.periode DESC
  LIMIT 1
) r
WHERE p.modalite_id IS NULL AND p.sexe = 'T' AND p.age_min IS NULL AND p.age_max IS NULL;

-- Parc locatif social (RPLS) : nombre de logements des bailleurs sociaux.
INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('SDES_RPLS', 'SDES (ministère chargé du Logement)',
   'Répertoire des logements locatifs des bailleurs sociaux (RPLS) : données détaillées',
   'https://www.statistiques.developpement-durable.gouv.fr/catalogue?page=dataset&datasetId=6390f7cb84f0679b04942fc2');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle)
SELECT 'LOGEMENTS_SOCIAUX', 'Logements sociaux',
       'Logements locatifs des bailleurs sociaux (offices et entreprises HLM, sociétés '
       'd''économie mixte pour leurs logements conventionnés) au 1er janvier.',
       'logements', 'effectif', source_id, NULL,
       'Parc des bailleurs sociaux, loués ou non ; le fichier ouvert ne donne ni les '
       'loyers ni la vacance.',
       NULL, 'BESOINS', 'LOGEMENT', 'ACCES'
FROM ref.source WHERE code = 'SDES_RPLS';
