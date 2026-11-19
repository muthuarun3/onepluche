-- Sources officielles retenues pour le MVP (dossier de conception, étapes 2 et 6).
INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_COG',  'INSEE', 'Code officiel géographique',
   'https://www.insee.fr/fr/information/7671867'),
  ('INSEE_EST',  'INSEE', 'Estimations de population par sexe et âge',
   'https://www.insee.fr/fr/statistiques/2012692'),
  ('INSEE_RP',   'INSEE', 'Recensement de la population',
   'https://www.insee.fr/fr/information/6654307'),
  ('INSEE_EC',   'INSEE', 'État civil : naissances et décès',
   'https://www.insee.fr/fr/statistiques/1893255'),
  ('INSEE_CHOM', 'INSEE', 'Taux de chômage localisés (au sens du BIT)',
   'https://insee.fr/fr/statistiques/1893230'),
  ('DREES_PENS', 'DREES', 'Effectifs de retraités (bénéficiaires d''une pension)',
   'https://drees.solidarites-sante.gouv.fr/publications-communique-de-presse-documents-de-reference/250731_PANORAMAS-retraites');
