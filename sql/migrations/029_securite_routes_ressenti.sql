-- Appli « Les Français sont-ils en sécurité ? », PR S2 : routes et ressenti.
-- Dossier de conception de l'appli sécurité, étapes 5 et 6.
-- Accidents corporels de la circulation (ONISR) : tués et blessés hospitalisés par
-- département du lieu de l'accident, et tués par million d'habitants (calculé avec la
-- population au 1er janvier). Sentiment d'insécurité (enquêtes CVS puis VRS), France
-- métropolitaine. Les taux de plainte attendent les rapports VRS (PDF).

INSERT INTO ref.unite (code) VALUES ('par_million');

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('ONISR_ACCIDENTS', 'Ministère de l''Intérieur (ONISR)',
   'Bases de données annuelles des accidents corporels de la circulation routière',
   'https://www.data.gouv.fr/fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2025/'),
  ('SSMSI_CVS', 'Insee et ministère de l''Intérieur (SSMSI)',
   'Indicateurs annuels de la victimation et du sentiment d''insécurité issus des enquêtes '
   'Cadre de vie et sécurité',
   'https://www.data.gouv.fr/fr/datasets/indicateurs-annuels-de-la-victimation-et-du-sentiment-dinsecurite-issus-des-enquetes-cadre-de-vie-et-securite/'),
  ('SSMSI_VRS', 'Ministère de l''Intérieur (SSMSI)',
   'Enquête Vécu et ressenti en matière de sécurité, chiffres recopiés des publications',
   'https://www.interieur.gouv.fr/Interstats/L-enquete-Vecu-et-ressenti-en-matiere-de-securite-VRS');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, borne_min,
                            borne_max)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'SECURITE', v.theme, v.borne_min, v.borne_max
FROM (VALUES
  ('ONISR_ACCIDENTS', 'TUES_ROUTE', 'Tués sur la route',
   'Personnes tuées dans un accident corporel de la circulation (décédées sur le coup ou '
   'dans les 30 jours), comptées dans le département de l''accident.',
   'nombre', 'flux', NULL,
   'Compté là où l''accident a lieu, pas là où vit la victime.', NULL, 'ROUTES', 0, NULL),
  ('ONISR_ACCIDENTS', 'BLESSES_HOSPITALISES_ROUTE', 'Blessés hospitalisés sur la route',
   'Personnes blessées dans un accident corporel de la circulation et hospitalisées plus '
   'de 24 heures, comptées dans le département de l''accident.',
   'nombre', 'flux', NULL,
   'Compté là où l''accident a lieu. Le nombre baisse fortement depuis 2016 (28 376 en '
   '2016, 19 289 en 2025) : la mesure de l''hospitalisation par les forces de l''ordre a '
   'changé, les années ne se comparent pas sûrement.',
   'Ne pas comparer dans le temps.', 'ROUTES', 0, NULL),
  ('ONISR_ACCIDENTS', 'TAUX_TUES_ROUTE', 'Tués sur la route par million d''habitants',
   'Personnes tuées dans un accident de la circulation dans le département, pour un '
   'million d''habitants au 1er janvier de l''année.',
   'par_million', 'taux', '1 000 000 × tués / population au 1er janvier (INSEE)',
   'Compté là où l''accident a lieu : un département traversé par de grands axes compte '
   'aussi les tués qui n''y habitent pas.', NULL, 'ROUTES', 0, 1000),
  ('SSMSI_CVS', 'PART_INSECURITE_QUARTIER',
   'Personnes qui se sentent en insécurité dans leur quartier',
   'Part des personnes qui se sentent souvent ou de temps en temps en insécurité dans '
   'leur quartier ou leur village.',
   'pourcentage', 'taux', NULL,
   'Jusqu''en 2019 : enquête Cadre de vie et sécurité, 14 ans ou plus, France '
   'métropolitaine. Depuis 2022 : enquête Vécu et ressenti, 18 ans ou plus (18-74 ans en '
   '2022), avec trois DROM à partir de 2024.',
   'Les deux enquêtes ne se comparent pas : la courbe est coupée entre 2019 et 2022.',
   'RESSENTI', 0, 100),
  ('SSMSI_CVS', 'PART_INSECURITE_DOMICILE', 'Personnes qui se sentent en insécurité chez elles',
   'Part des personnes qui se sentent souvent ou de temps en temps en insécurité à leur '
   'domicile.',
   'pourcentage', 'taux', NULL,
   'Jusqu''en 2019 : enquête Cadre de vie et sécurité, 14 ans ou plus, France '
   'métropolitaine. Depuis 2022 : enquête Vécu et ressenti, 18 ans ou plus (18-74 ans en '
   '2022), avec trois DROM à partir de 2024.',
   'Les deux enquêtes ne se comparent pas : la courbe est coupée entre 2019 et 2022.',
   'RESSENTI', 0, 100),
  ('SSMSI_CVS', 'PART_RENONCE_SORTIR',
   'Personnes qui renoncent à sortir seules pour leur sécurité',
   'Part des personnes à qui il arrive de renoncer à sortir seules de chez elles pour des '
   'raisons de sécurité.',
   'pourcentage', 'taux', NULL,
   'Jusqu''en 2019 : enquête Cadre de vie et sécurité, 14 ans ou plus, France '
   'métropolitaine. Depuis 2022 : enquête Vécu et ressenti, 18 ans ou plus (18-74 ans en '
   '2022), avec trois DROM à partir de 2024.',
   'Les deux enquêtes ne se comparent pas : la courbe est coupée entre 2019 et 2022.',
   'RESSENTI', 0, 100)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement,
        comparabilite, theme, borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;

-- Tués par million d'habitants : tués de l'année / population au 1er janvier de la même
-- année (estimations INSEE). Pas de valeur tant que la population de l'année manque.
CREATE VIEW stat.securite_derives AS
SELECT 'TAUX_TUES_ROUTE'::text AS indicateur,
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int AS annee,
       round(1000000 * o.valeur / p.population, 1) AS valeur,
       o.statut = 'PROVISOIRE' OR p.provisoire AS provisoire,
       'T'::char(1) AS sexe,
       o.periode,
       o.periode_type
FROM stat.observation o
JOIN ref.indicateur i ON i.indicateur_id = o.indicateur_id AND i.code = 'TUES_ROUTE'
JOIN stat.structure_age p ON p.territoire_id = o.territoire_id AND p.periode = o.periode
JOIN ref.territoire t ON t.territoire_id = o.territoire_id
WHERE o.sexe = 'T' AND o.age_min IS NULL AND o.age_max IS NULL AND o.modalite_id IS NULL
  AND p.population > 0;

-- La vue lue par l'application ajoute ces indicateurs calculés (définition de la
-- migration 018, plus la dernière branche).
CREATE OR REPLACE VIEW api.serie AS
SELECT v.indicateur,
       t.niveau,
       t.code,
       extract(year FROM s.periode)::int AS annee,
       v.valeur,
       s.provisoire,
       'T'::char(1) AS sexe,
       s.periode,
       '1ER_JANVIER'::text AS periode_type
FROM stat.structure_age s
JOIN ref.territoire t USING (territoire_id)
CROSS JOIN LATERAL (VALUES
  ('POP', s.population),
  ('PART_MOINS_20', round(100 * s.moins_20 / nullif(s.population, 0), 2)),
  ('PART_60_PLUS', round(100 * s.plus_60 / nullif(s.population, 0), 2)),
  ('PART_75_PLUS', round(100 * s.plus_75 / nullif(s.population, 0), 2)),
  ('INDICE_VIEILLISSEMENT', round(100 * s.plus_65 / nullif(s.moins_20, 0), 1))
) AS v (indicateur, valeur)
WHERE v.valeur IS NOT NULL
UNION ALL
-- Indicateurs publiés tels quels par la source (hors population, déjà ci-dessus).
SELECT i.code,
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int,
       o.valeur,
       o.statut = 'PROVISOIRE',
       o.sexe,
       o.periode,
       o.periode_type
FROM stat.observation o
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
WHERE i.code <> 'POP'
  AND o.age_min IS NULL AND o.age_max IS NULL AND o.modalite_id IS NULL
UNION ALL
SELECT 'SOLDE_NATUREL',
       t.niveau,
       t.code,
       extract(year FROM n.periode)::int,
       n.valeur - d.valeur,
       n.statut = 'PROVISOIRE' OR d.statut = 'PROVISOIRE',
       'T',
       n.periode,
       n.periode_type
FROM stat.observation n
JOIN ref.indicateur ni ON ni.indicateur_id = n.indicateur_id AND ni.code = 'NAISSANCES'
JOIN stat.observation d
  ON d.territoire_id = n.territoire_id AND d.periode = n.periode AND d.sexe = n.sexe
 AND d.age_min IS NULL AND d.age_max IS NULL AND d.modalite_id IS NULL
JOIN ref.indicateur di ON di.indicateur_id = d.indicateur_id AND di.code = 'DECES'
JOIN ref.territoire t ON t.territoire_id = n.territoire_id
WHERE n.sexe = 'T' AND n.age_min IS NULL AND n.age_max IS NULL AND n.modalite_id IS NULL
UNION ALL
-- Recensement : effectifs et taux d'activité déduits de la population par statut d'activité.
SELECT v.indicateur,
       t.niveau,
       t.code,
       extract(year FROM r.periode)::int,
       v.valeur,
       false,
       'T',
       r.periode,
       'RP'
FROM (
  SELECT o.territoire_id,
         o.periode,
         sum(o.valeur) FILTER (WHERE o.age_max = 64 AND m.code IS NULL) AS pop_15_64,
         sum(o.valeur) FILTER (WHERE o.age_max = 64 AND m.code = 'ACTIF') AS actifs,
         sum(o.valeur) FILTER (WHERE o.age_max = 64 AND m.code = 'INACTIF') AS inactifs,
         sum(o.valeur) FILTER (WHERE o.age_max IS NULL AND m.code = 'RETRAITE') AS retraites
  FROM stat.observation o
  JOIN ref.indicateur i USING (indicateur_id)
  LEFT JOIN ref.modalite m USING (modalite_id)
  WHERE i.code = 'POP_RP' AND o.sexe = 'T' AND o.age_min = 15
  GROUP BY o.territoire_id, o.periode
) r
JOIN ref.territoire t USING (territoire_id)
CROSS JOIN LATERAL (VALUES
  ('ACTIFS_15_64', round(r.actifs)),
  ('INACTIFS_15_64', round(r.inactifs)),
  ('RETRAITES_RP', round(r.retraites)),
  ('TAUX_ACTIVITE_15_64', round(100 * r.actifs / nullif(r.pop_15_64, 0), 1))
) AS v (indicateur, valeur)
WHERE v.valeur IS NOT NULL
UNION ALL
-- Retraités pour 100 actifs : pensionnés (DREES, national) rapportés aux actifs de 15 à
-- 64 ans du recensement de la même année.
SELECT 'PENSIONNES_POUR_100_ACTIFS',
       t.niveau,
       t.code,
       extract(year FROM p.periode)::int,
       round(100 * p.valeur / nullif(a.actifs, 0), 1),
       p.statut = 'PROVISOIRE',
       'T',
       p.periode,
       'RP'
FROM stat.observation p
JOIN ref.indicateur pi ON pi.indicateur_id = p.indicateur_id AND pi.code = 'PENSIONNES'
JOIN (
  SELECT o.territoire_id, o.periode, sum(o.valeur) AS actifs
  FROM stat.observation o
  JOIN ref.indicateur i USING (indicateur_id)
  JOIN ref.modalite m USING (modalite_id)
  WHERE i.code = 'POP_RP' AND o.sexe = 'T' AND o.age_min = 15 AND o.age_max = 64
    AND m.code = 'ACTIF'
  GROUP BY o.territoire_id, o.periode
) a ON a.territoire_id = p.territoire_id AND a.periode = p.periode
JOIN ref.territoire t ON t.territoire_id = p.territoire_id
WHERE p.sexe = 'T' AND p.age_min IS NULL AND p.age_max IS NULL AND p.modalite_id IS NULL
UNION ALL
-- Taux de scolarisation des 18-24 ans (recensement).
SELECT 'TAUX_SCOLARISATION_18_24',
       t.niveau,
       t.code,
       extract(year FROM s.periode)::int,
       round(100 * s.valeur / nullif(p.valeur, 0), 1),
       false,
       'T',
       s.periode,
       'RP'
FROM stat.observation s
JOIN ref.indicateur i ON i.indicateur_id = s.indicateur_id AND i.code = 'POP_SCOLARISATION'
JOIN ref.modalite m ON m.modalite_id = s.modalite_id AND m.code = 'SCOLARISE'
JOIN stat.observation p
  ON p.indicateur_id = s.indicateur_id AND p.territoire_id = s.territoire_id
 AND p.periode = s.periode AND p.sexe = s.sexe
 AND p.age_min = 18 AND p.age_max = 24 AND p.modalite_id IS NULL
JOIN ref.territoire t ON t.territoire_id = s.territoire_id
WHERE s.sexe = 'T' AND s.age_min = 18 AND s.age_max = 24
UNION ALL
-- Appli 2 : indicateurs calculés de la rubrique « besoins ».
SELECT indicateur, niveau, code, annee, valeur, provisoire, sexe, periode, periode_type
FROM stat.besoins_derives
UNION ALL
-- Appli sécurité : indicateurs calculés (tués sur la route par million d'habitants).
SELECT indicateur, niveau, code, annee, valeur, provisoire, sexe, periode, periode_type
FROM stat.securite_derives;
