-- Qui sont les Français ? Étape 2 : étudiants de l'enseignement supérieur, par type de
-- formation et, à l'université, par grande discipline (ministère de l'Enseignement
-- supérieur, au département de l'établissement).

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('MESR_ETU', 'Ministère de l''Enseignement supérieur',
   'Effectifs d''étudiants inscrits dans l''enseignement supérieur',
   'https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits_agregeables/');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('formation', 'UNIVERSITES', 'Universités et grands établissements'),
  ('formation', 'STS', 'Sections de techniciens supérieurs (BTS)'),
  ('formation', 'CPGE', 'Classes préparatoires aux grandes écoles'),
  ('formation', 'INGENIEURS', 'Écoles d''ingénieurs (hors universités)'),
  ('formation', 'COMMERCE', 'Écoles de commerce, gestion et comptabilité'),
  ('formation', 'PARAMEDICAL_SOCIAL', 'Écoles paramédicales et sociales'),
  ('formation', 'ART_CULTURE', 'Écoles d''art et de culture'),
  ('formation', 'AUTRES_ECOLES', 'Autres écoles (ENS, juridiques, spécialités diverses)'),
  ('discipline', 'DROIT_ECO_GESTION', 'Droit, économie, gestion, AES'),
  ('discipline', 'LETTRES_SHS', 'Lettres, langues, sciences humaines et sociales'),
  ('discipline', 'SCIENCES', 'Sciences et sciences de l''ingénieur'),
  ('discipline', 'SANTE', 'Santé'),
  ('discipline', 'STAPS', 'Sport (STAPS)'),
  ('discipline', 'AUTRES_DISCIPLINES', 'Interdisciplinaire, théologie');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id,
                            avertissement, comparabilite)
SELECT v.code, v.libelle, v.definition, 'personnes', 'effectif', s.source_id,
       v.avertissement, v.comparabilite
FROM ref.source s
CROSS JOIN (VALUES
  ('ETUDIANTS', 'Étudiants inscrits dans l''enseignement supérieur',
   'Inscriptions dans l''enseignement supérieur (universités, BTS, classes '
   'préparatoires, écoles…), à la rentrée de l''année indiquée.',
   'Compté au département de l''établissement, pas du domicile : les villes '
   'universitaires concentrent les effectifs. Un étudiant inscrit dans deux formations '
   'peut être compté deux fois.',
   'Série homogène depuis la rentrée 2001.'),
  ('ETUDIANTS_UNIVERSITE', 'Étudiants des universités par discipline',
   'Inscriptions dans les universités publiques, par grande discipline, à la rentrée '
   'de l''année indiquée.',
   'Universités publiques seulement (environ la moitié des étudiants). Compté au '
   'département du site d''enseignement.',
   'Série depuis la rentrée 2017.')
) AS v (code, libelle, definition, avertissement, comparabilite)
WHERE s.code = 'MESR_ETU';
