-- Appli 2, phase D : vue d'ensemble « budget des ménages ». Dossier de conception de
-- l'appli 2, étape 8 (écran /besoins). Comptes nationaux de l'INSEE, France entière :
-- dépense de consommation des ménages par poste et part des dépenses pré-engagées dans
-- leur revenu. Ces indicateurs couvrent tous les thèmes : thème « BUDGET ».

ALTER TABLE ref.indicateur DROP CONSTRAINT indicateur_theme_check;
ALTER TABLE ref.indicateur ADD CONSTRAINT indicateur_theme_check
  CHECK (theme IN ('BUDGET', 'LOGEMENT', 'ENERGIE', 'EAU', 'ALIMENTATION', 'TRANSPORTS',
                   'SOINS', 'NUMERIQUE', 'GARDE'));

ALTER TABLE ref.indicateur DROP CONSTRAINT indicateur_unite_check;
ALTER TABLE ref.indicateur ADD CONSTRAINT indicateur_unite_check
  CHECK (unite IN ('personnes', 'pourcentage', 'pour_mille', 'ratio', 'annees',
                   'logements', 'nombre', 'euros', 'euros_m2', 'mwh', 'indice',
                   'consultations_hab', 'pour_10000', 'millions_euros'));

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_CNA', 'INSEE',
   'Comptes nationaux annuels : consommation des ménages par fonction',
   'https://www.insee.fr/fr/statistiques/series/102342913');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('poste_conso', 'ALIMENTATION', 'Alimentation et boissons non alcoolisées'),
  ('poste_conso', 'ALCOOL_TABAC', 'Alcool et tabac'),
  ('poste_conso', 'HABILLEMENT', 'Habillement et chaussures'),
  ('poste_conso', 'LOGEMENT', 'Logement, eau, gaz, électricité, combustibles'),
  ('poste_conso', 'EQUIPEMENT_MAISON', 'Meubles et entretien de la maison'),
  ('poste_conso', 'SANTE', 'Santé'),
  ('poste_conso', 'TRANSPORTS', 'Transports'),
  ('poste_conso', 'COMMUNICATION', 'Information et communication'),
  ('poste_conso', 'LOISIRS', 'Loisirs, sport et culture'),
  ('poste_conso', 'ENSEIGNEMENT', 'Enseignement'),
  ('poste_conso', 'RESTAURANTS_HOTELS', 'Restaurants et hôtels'),
  ('poste_conso', 'ASSURANCES_FINANCE', 'Assurances et services financiers'),
  ('poste_conso', 'AUTRES', 'Soins corporels et autres dépenses');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, NULL, 'BESOINS', 'BUDGET', v.angle,
       v.borne_min, v.borne_max, NULL
FROM (VALUES
  ('DEPENSE_CONSO_MENAGES', 'Dépense de consommation des ménages',
   'Ce que les ménages résidant en France dépensent dans l''année pour leur '
   'consommation, par poste, en millions d''euros courants.',
   'millions_euros', 'flux', NULL,
   'Comptes nationaux : les loyers « imputés » des propriétaires occupants sont comptés '
   'dans le logement. Les dépenses de santé ou d''éducation payées par la Sécurité '
   'sociale ou l''État n''y sont pas. Les trois dernières années sont provisoires.',
   NULL, 0, NULL),
  ('PART_DEPENSE_PRE_ENGAGEE', 'Dépenses pré-engagées',
   'Part du revenu disponible des ménages déjà engagée par contrat avant toute autre '
   'dépense : logement, énergie, eau, assurances, abonnements de télévision, téléphone '
   'et internet, cantines, services financiers.',
   'pourcentage', 'taux', '100 × dépenses pré-engagées / revenu disponible brut',
   'Moyenne de tous les ménages ; elle pèse plus lourd chez les ménages modestes.',
   'COUT', 0, 100)
) AS v (code, libelle, definition, unite, nature, formule, avertissement, angle,
        borne_min, borne_max)
JOIN ref.source s ON s.code = 'INSEE_CNA';
