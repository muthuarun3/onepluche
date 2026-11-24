-- Appli 5 « Quel avenir pour les Français ? », phase C : risques naturels.
--
-- Source : base GASPAR du ministère de la Transition écologique (Géorisques), archive
-- publique gaspar.zip, mise à jour chaque mois, sans compte. Deux de ses fichiers :
-- - catnat : chaque reconnaissance de l'état de catastrophe naturelle d'une commune
--   (arrêté × commune × péril) depuis 1982 ;
-- - pprn : les plans de prévention des risques naturels, commune par commune.
-- Les communes sont ramenées au département par leur code (maille du projet).
-- Ce sont des faits observés : ils vont dans stat.observation, pas dans stat.projection.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('GEORISQUES_GASPAR', 'Ministère de la Transition écologique (Géorisques)',
   'Base GASPAR : catastrophes naturelles reconnues et plans de prévention des risques',
   'https://www.georisques.gouv.fr/donnees/bases-de-donnees/base-gaspar');

-- Périls des arrêtés, regroupés (code GASPAR entre parenthèses dans le connecteur).
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('peril_catnat', 'INONDATION', 'Inondations et coulées de boue'),
  ('peril_catnat', 'SECHERESSE', 'Sécheresse (retrait-gonflement des argiles)'),
  ('peril_catnat', 'MOUVEMENT_TERRAIN', 'Mouvements de terrain'),
  ('peril_catnat', 'VAGUES', 'Vagues et submersion marine'),
  ('peril_catnat', 'TEMPETE', 'Tempêtes et cyclones'),
  ('peril_catnat', 'AUTRES', 'Autres (séisme, avalanche, grêle, neige…)');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme,
                            borne_min, borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'AVENIR', 'RISQUES', v.borne_min, v.borne_max
FROM (VALUES
  ('CATNAT_ARRETES', 'Catastrophes naturelles reconnues',
   'Nombre de reconnaissances de l''état de catastrophe naturelle : une par commune, par '
   'péril et par événement reconnu dans un arrêté, rangée l''année où l''événement a '
   'commencé.',
   'nombre', 'flux', NULL,
   'Une reconnaissance est demandée par la commune et accordée par arrêté, souvent plus '
   'd''un an après l''événement : les deux dernières années sont incomplètes. Elle ouvre '
   'l''indemnisation des assurés ; elle ne mesure ni l''ampleur ni le coût des dégâts.',
   'Depuis 1982. Une commune touchée par deux périls dans le même arrêté compte deux fois.',
   0, 100000),
  ('CATNAT_SECHERESSE_10ANS', 'Communes reconnues en sécheresse en 10 ans',
   'Part des communes reconnues au moins une fois en catastrophe naturelle « sécheresse » '
   '(retrait-gonflement des argiles) pour un événement des dix années qui finissent cette '
   'année-là.',
   'pourcentage', 'taux',
   'Communes reconnues en sécheresse pour un événement des années N-9 à N / communes du '
   'département (code officiel géographique 2025) × 100',
   'Seules les communes bâties sur des sols argileux peuvent être reconnues : la part '
   'dépend du sol autant que du climat.',
   'Communes actuelles (code officiel géographique 2025), une commune fusionnée comptant '
   'pour une.', 0, 100),
  ('COMMUNES_PPRN', 'Communes couvertes par un plan de prévention',
   'Part des communes où s''applique au moins un plan de prévention des risques naturels '
   'approuvé (inondation, mouvement de terrain, avalanche, feu de forêt, séisme…).',
   'pourcentage', 'taux',
   'Communes avec un PPRN approuvé en vigueur / communes du département (code officiel '
   'géographique 2025) × 100',
   'Un plan de prévention règle la construction dans les zones exposées : son absence ne '
   'veut pas dire absence de risque.',
   'État de la base GASPAR à la date du fichier.', 0, 100)
) AS v (code, libelle, definition, unite, nature, formule, avertissement, comparabilite,
        borne_min, borne_max)
JOIN ref.source s ON s.code = 'GEORISQUES_GASPAR';
