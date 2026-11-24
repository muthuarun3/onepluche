-- Appli « Comment travaillent les Français ? », PR T5 : télétravail (enquête Emploi, France)
-- et accidents du travail (Assurance maladie, régions). Les grèves et l'audience syndicale
-- attendent une source téléchargeable. Dossier de conception de l'appli travail, étape 5.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_EEC', 'INSEE',
   'Enquête Emploi : activité, emploi et chômage, résultats annuels',
   'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DD_EEC_ANNUEL'),
  ('CNAM_RISQUES_PRO', 'Assurance maladie',
   'Risques professionnels : sinistralité par région administrative',
   'https://data.ameli.fr/explore/dataset/sinistralite-par-region-administrative/');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme,
                            borne_min, borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'TRAVAIL', v.theme, v.borne_min, v.borne_max
FROM (VALUES
  ('INSEE_EEC', 'PART_TELETRAVAIL', 'Part des personnes qui télétravaillent',
   'Personnes en emploi ayant télétravaillé au moins un jour par semaine pendant les '
   'quatre dernières semaines travaillées, pour 100 personnes en emploi. Au total et par '
   'catégorie socioprofessionnelle.',
   'pourcentage', 'taux', 'TELETRAVAIL', NULL,
   'Enquête Emploi : France hors Mayotte seulement, pas de chiffre par département. '
   'L''INSEE ne publie en ligne que la dernière année.',
   'Un seul millésime en ligne : pas d''évolution.', 0, 60),
  ('CNAM_RISQUES_PRO', 'ACCIDENTS_TRAVAIL', 'Accidents du travail',
   'Accidents du travail avec arrêt reconnus dans l''année par l''Assurance maladie, '
   'pour les salariés du régime général (hors fonction publique et agriculture).',
   'nombre', 'flux', 'ACCIDENTS', NULL,
   'Régime général seulement : fonctionnaires, salariés agricoles et indépendants ne sont '
   'pas comptés. Par région de l''établissement employeur.',
   'Série depuis 2005.', 0, 1000000),
  ('CNAM_RISQUES_PRO', 'INDICE_FREQUENCE_AT', 'Accidents du travail pour 1 000 salariés',
   'Accidents du travail avec arrêt reconnus dans l''année pour 1 000 salariés du régime '
   'général (indice de fréquence).',
   'pour_mille', 'ratio', 'ACCIDENTS', '1 000 × accidents du travail / salariés',
   'Régime général seulement. Dépend beaucoup des métiers de la région (construction, '
   'logistique, soins).',
   'Comparable entre régions et dans le temps.', 5, 80),
  ('CNAM_RISQUES_PRO', 'ACCIDENTS_TRAJET', 'Accidents de trajet',
   'Accidents survenus sur le trajet entre le domicile et le travail, avec arrêt, reconnus '
   'dans l''année, pour les salariés du régime général.',
   'nombre', 'flux', 'ACCIDENTS', NULL,
   'Régime général seulement.', 'Série depuis 2005.', 0, 200000),
  ('CNAM_RISQUES_PRO', 'MALADIES_PROFESSIONNELLES', 'Maladies professionnelles',
   'Maladies professionnelles reconnues dans l''année (troubles musculosquelettiques, '
   'amiante…), pour les salariés du régime général.',
   'nombre', 'flux', 'ACCIDENTS', NULL,
   'Régime général seulement. Une maladie est comptée l''année de sa reconnaissance, '
   'parfois longtemps après l''exposition.',
   'Série depuis 2005 ; les tableaux de maladies reconnues évoluent.', 0, 200000)
) AS v (source, code, libelle, definition, unite, nature, theme, formule, avertissement,
        comparabilite, borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;
