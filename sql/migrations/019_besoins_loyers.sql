-- Appli 2, phase B : loyers d'annonce (Carte des loyers, ANIL). Dossier de conception de
-- l'appli 2, étapes 5 et 6. Les indicateurs communaux sont ramenés au département, à la
-- région et à la France dans le connecteur, en moyenne pondérée par les résidences
-- principales louées de chaque commune (recensement, ingest.poids_commune).
-- Un indicateur pour les appartements, un pour les maisons : la source ne publie pas de
-- loyer « tous logements ».

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('ANIL_LOYERS', 'ANIL',
   'Carte des loyers : estimations ANIL, à partir des données du Groupe SeLoger et de '
   'leboncoin',
   'https://www.data.gouv.fr/datasets/?q=carte%20des%20loyers');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('taille_appartement', 'T1_T2', 'Appartements d''une ou deux pièces'),
  ('taille_appartement', 'T3_PLUS', 'Appartements de trois pièces ou plus');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, 'euros_m2', 'prix', s.source_id, v.formule,
       'Loyers d''annonces (logements vides, charges comprises), pas loyers de tous '
       'les locataires en place. Dans les petites communes sans annonce, le loyer est '
       'celui estimé pour un groupe de communes voisines semblables.',
       'Chaque édition réestime toute la carte : l''ANIL déconseille de comparer deux '
       'éditions entre elles.',
       'BESOINS', 'LOGEMENT', 'COUT', 3, 60, 0.15
FROM (VALUES
  ('LOYER_APPARTEMENT_M2', 'Loyer d''annonce d''un appartement',
   'Loyer mensuel charges comprises, en euros par m², d''un appartement type loué vide '
   '(52 m², 22 m² par pièce), mis en location au 3e trimestre de l''année.',
   'Moyenne des loyers communaux pondérée par les résidences principales louées de '
   'chaque commune'),
  ('LOYER_MAISON_M2', 'Loyer d''annonce d''une maison',
   'Loyer mensuel charges comprises, en euros par m², d''une maison type louée vide '
   '(92 m², 22 m² par pièce), mise en location au 3e trimestre de l''année.',
   'Moyenne des loyers communaux pondérée par les résidences principales louées de '
   'chaque commune')
) AS v (code, libelle, definition, formule)
CROSS JOIN ref.source s
WHERE s.code = 'ANIL_LOYERS';
