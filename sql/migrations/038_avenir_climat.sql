-- Appli 5 « Quel avenir pour les Français ? », phase B : climat.
--
-- Source : Banque mondiale, Climate Change Knowledge Portal (CCKP), projections CMIP6 du
-- sixième rapport du GIEC, ramenées à une grille de 0,25° (environ 25 km) et corrigées de
-- leurs biais (méthode NASA NEX-GDDP-CMIP6). Fichiers publics, sans compte. Elle remplace
-- DRIAS-2020 prévu au dossier (étape 6) : DRIAS demande un compte nominatif et une
-- extraction à la main, ce que Muthu ne souhaite pas (22/11/2026).
--
-- Chaque valeur est un écart à la période de référence 1995-2014, moyenne sur 20 ans
-- (2020-2039, 2040-2059, 2060-2079, 2080-2099), pour un scénario d'émissions SSP. Médiane
-- de l'ensemble des modèles (MEDIANE) et fourchette : 10e centile (BAS), 90e (HAUT).
-- La valeur d'un département est la moyenne de ses mailles, pondérée par sa surface dans
-- chaque maille ; la France métropolitaine (FM) est la moyenne des départements pondérée
-- par leur surface. Pas d'outre-mer : la grille est trop grossière pour ces îles.

INSERT INTO ref.scenario (code, libelle, famille, description, equivalent_giec, ordre) VALUES
  ('GIEC_SSP126', 'Émissions fortement réduites (SSP1-2.6)', 'GIEC',
   'Les émissions mondiales baissent vite et deviennent nulles vers 2070 : l''objectif de '
   'l''accord de Paris est presque tenu.', '+1,8 °C', 11),
  ('GIEC_SSP245', 'Émissions intermédiaires (SSP2-4.5)', 'GIEC',
   'Les émissions restent proches du niveau actuel jusqu''en 2050, puis baissent lentement : '
   'la trajectoire des politiques annoncées.', '+2,7 °C', 12),
  ('GIEC_SSP585', 'Émissions très élevées (SSP5-8.5)', 'GIEC',
   'Les émissions doublent d''ici 2050 : le scénario le plus pessimiste du GIEC.',
   '+4,4 °C', 13);

INSERT INTO ref.unite (code) VALUES ('degres_c'), ('jours'), ('millimetres');

INSERT INTO ref.source (code, producteur, libelle, url, licence) VALUES
  ('BM_CMIP6', 'Banque mondiale',
   'Projections climatiques CMIP6 à 0,25° (Climate Change Knowledge Portal)',
   'https://climateknowledgeportal.worldbank.org/',
   'CC BY 4.0 (Banque mondiale) ; données des modèles CMIP6, CC BY-SA 4.0');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme,
                            borne_min, borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, 'taux', s.source_id, NULL,
       'Une projection n''est pas une prévision. Écart moyen sur 20 ans à la période '
       '1995-2014, selon les modèles climatiques mondiaux du GIEC (CMIP6) ramenés à une '
       'grille de 25 km : les petits départements (Paris et la petite couronne) sont décrits '
       'grossièrement, le relief et le littoral lissés.',
       'Comparable entre départements et avec la France métropolitaine, dans le même '
       'scénario et pour la même période.',
       'AVENIR', 'CLIMAT', v.borne_min, v.borne_max
FROM (VALUES
  ('CLIM_TAS', 'Réchauffement moyen',
   'Écart de la température moyenne annuelle à celle de 1995-2014, en degrés.',
   'degres_c', -5, 15),
  ('CLIM_HD35', 'Jours de forte chaleur en plus',
   'Écart du nombre de jours par an où la température maximale atteint 35 °C ou plus.',
   'jours', -50, 200),
  ('CLIM_TR', 'Nuits tropicales en plus',
   'Écart du nombre de nuits par an où la température ne descend pas sous 20 °C.',
   'jours', -50, 250),
  ('CLIM_FD', 'Jours de gel en moins ou en plus',
   'Écart du nombre de jours par an où la température minimale passe sous 0 °C '
   '(négatif : moins de gel).', 'jours', -250, 50),
  ('CLIM_PR', 'Pluie sur l''année',
   'Écart du cumul annuel de précipitations, en millimètres.', 'millimetres', -1500, 1500),
  ('CLIM_R20MM', 'Jours de fortes pluies en plus',
   'Écart du nombre de jours par an avec au moins 20 mm de pluie.', 'jours', -50, 50),
  ('CLIM_CDD', 'Plus longue période sèche',
   'Écart de la plus longue suite de jours secs (moins de 1 mm de pluie) dans l''année, '
   'en jours.', 'jours', -100, 200)
) AS v (code, libelle, definition, unite, borne_min, borne_max)
JOIN ref.source s ON s.code = 'BM_CMIP6';

-- Climat d'un territoire : une ligne par indicateur, scénario et période, avec la médiane
-- et la fourchette (10e et 90e centiles des modèles).
CREATE VIEW api.projection_climat AS
SELECT p.indicateur, p.niveau, p.code, p.scenario,
       extract(year FROM p.periode)::int AS debut, extract(year FROM p.periode_fin)::int AS fin,
       max(p.valeur) FILTER (WHERE p.statistique = 'MEDIANE') AS mediane,
       max(p.valeur) FILTER (WHERE p.statistique = 'BAS') AS bas,
       max(p.valeur) FILTER (WHERE p.statistique = 'HAUT') AS haut
FROM api.projection p
JOIN ref.indicateur i ON i.code = p.indicateur AND i.theme = 'CLIMAT'
GROUP BY p.indicateur, p.niveau, p.code, p.scenario, p.periode, p.periode_fin;
