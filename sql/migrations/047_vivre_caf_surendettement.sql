-- Appli « Comment vivent les Français ? » (rubrique /vivre), phase B : allocataires des
-- CAF (RSA, aides au logement, décembre de chaque année), surendettement (Banque de France)
-- et quatre indicateurs calculés par On épluche. Dossier de conception, étapes 5 et 6
-- (validées le 22/11/2026).

INSERT INTO ref.source (code, producteur, libelle, url, licence) VALUES
  ('CNAF', 'CNAF',
   'Allocataires des caisses d''allocations familiales (régime général)',
   'https://data.caf.fr', 'Licence Ouverte 2.0 (Etalab)'),
  ('BDF_SUREN', 'Banque de France',
   'Enquête typologique sur le surendettement des ménages',
   'https://www.banque-france.fr/fr/publications-et-statistiques/publications/'
   'typologie-du-surendettement-des-menages-2025',
   'Réutilisation libre, en citant la Banque de France et la date de mise à jour');

INSERT INTO ref.unite (code) VALUES ('pour_100000');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('logement_aide', 'LOCATION', 'Locataires'),
  ('logement_aide', 'ACCESSION', 'Accédants à la propriété'),
  ('logement_aide', 'FOYER', 'Résidents d''un foyer (étudiants, jeunes travailleurs, '
                            'personnes âgées…)'),
  ('type_dette', 'HORS_IMMOBILIER', 'Toutes dettes hors immobilier'),
  ('type_dette', 'IMMOBILIER', 'Dettes immobilières'),
  ('type_dette', 'CONSOMMATION', 'Crédits à la consommation'),
  ('type_dette', 'CHARGES_COURANTES', 'Charges courantes (loyer, énergie, eau, téléphone…)');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, rubrique, theme, borne_min, borne_max,
                            seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, 'VIVRE', v.theme, v.borne_min, v.borne_max, NULL
FROM (VALUES
  -- CAF : situation en décembre.
  ('CNAF', 'FOYERS_RSA', 'Foyers au RSA',
   'Foyers bénéficiaires du revenu de solidarité active versé par la CAF, en décembre.',
   'nombre', 'effectif', NULL,
   'Régime général seul : les foyers relevant de la MSA (agriculteurs) ne sont pas comptés. '
   'France : somme des départements, calculée par On épluche.',
   'INEGALITES', 0, 3000000),
  ('CNAF', 'FOYERS_AIDES_LOGEMENT', 'Foyers aidés pour leur logement',
   'Foyers bénéficiaires d''une aide personnelle au logement (APL, ALF ou ALS) versée par '
   'la CAF, en décembre, selon qu''ils louent, achètent leur logement ou vivent en foyer.',
   'nombre', 'effectif', NULL,
   'Régime général seul (hors MSA). France : somme des départements, calculée par On '
   'épluche.',
   'AIDES_LOGEMENT', 0, 10000000),
  ('CNAF', 'MONTANT_AIDES_LOGEMENT', 'Aides au logement versées dans le mois',
   'Montant des aides personnelles au logement versées par la CAF au titre de décembre, en '
   'euros.',
   'euros', 'flux', NULL,
   'Régime général seul (hors MSA). France : somme des départements, calculée par On '
   'épluche.',
   'AIDES_LOGEMENT', 0, 5000000000),
  -- Banque de France.
  ('BDF_SUREN', 'DOSSIERS_SURENDETTEMENT', 'Dossiers de surendettement traités',
   'Dossiers de surendettement traités dans l''année par la commission du département.',
   'nombre', 'effectif', NULL,
   'Hors outre-mer (dossiers suivis par l''IEDOM). France métropolitaine : somme des '
   'départements, calculée par On épluche.',
   'EPARGNE', 0, 300000),
  ('BDF_SUREN', 'ENDETTEMENT_MEDIAN', 'Endettement médian des ménages surendettés',
   'Montant des dettes qui partage en deux moitiés les dossiers de surendettement traités '
   'dans l''année, toutes dettes confondues ou par grande famille de dettes (parmi les '
   'dossiers qui en comptent).',
   'euros', 'ratio', NULL, 'Hors outre-mer. Pas de valeur nationale.',
   'EPARGNE', 1, 1000000),
  -- Calculs d'On épluche (vue stat.vivre_derives).
  ('CNAF', 'FOYERS_RSA_POUR_1000', 'Foyers au RSA pour 1 000 habitants',
   'Foyers bénéficiaires du RSA en décembre pour 1 000 habitants au 1er janvier suivant.',
   'pour_mille', 'taux',
   'calcul On épluche : 1 000 × foyers au RSA en décembre / population au 1er janvier suivant',
   'Un foyer compte une ou plusieurs personnes. Régime général seul (hors MSA).',
   'INEGALITES', 0, 200),
  ('BDF_SUREN', 'SURENDETTEMENT_POUR_100000',
   'Dossiers de surendettement pour 100 000 habitants',
   'Dossiers de surendettement traités dans l''année pour 100 000 habitants au 1er janvier.',
   'pour_100000', 'taux',
   'calcul On épluche : 100 000 × dossiers traités / population au 1er janvier de l''année',
   'La Banque de France publie un ratio voisin sur les dossiers déposés : les deux ne se '
   'comparent pas exactement.',
   'EPARGNE', 0, 2000),
  ('CNAF', 'AIDE_LOGEMENT_MOYENNE', 'Aide au logement moyenne par foyer',
   'Montant moyen de l''aide au logement versée en décembre à un foyer bénéficiaire, en '
   'euros par mois.',
   'euros', 'ratio',
   'calcul On épluche : montant versé en décembre / foyers bénéficiaires', NULL,
   'AIDES_LOGEMENT', 0, 1000),
  ('INSEE_BTS', 'ECART_SALAIRE_FEMMES_HOMMES', 'Écart de salaire entre femmes et hommes',
   'De combien le salaire net moyen des femmes est inférieur à celui des hommes, en % du '
   'salaire des hommes (secteur privé, équivalent temps plein).',
   'pourcentage', 'taux',
   'calcul On épluche : 100 × (salaire des hommes − salaire des femmes) / salaire des hommes',
   'Écart moyen, toutes catégories confondues : il mêle les différences de métier, de '
   'catégorie et d''âge, et ne mesure pas l''écart à poste égal.',
   'REVENUS', -50, 80)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement, theme,
        borne_min, borne_max)
JOIN ref.source s ON s.code = v.source;

-- Indicateurs calculés. Les foyers au RSA de décembre sont rapportés à la population du
-- 1er janvier suivant ; les dossiers de surendettement de l'année à celle du 1er janvier
-- de l'année. Pas de valeur tant que la population manque.
CREATE VIEW stat.vivre_derives AS
SELECT 'FOYERS_RSA_POUR_1000'::text AS indicateur,
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int AS annee,
       round(1000 * o.valeur / p.population, 1) AS valeur,
       p.provisoire,
       'T'::char(1) AS sexe,
       o.periode,
       o.periode_type
FROM stat.observation o
JOIN ref.indicateur i ON i.indicateur_id = o.indicateur_id AND i.code = 'FOYERS_RSA'
JOIN stat.structure_age p
  ON p.territoire_id = o.territoire_id AND p.periode = (o.periode + interval '1 month')::date
JOIN ref.territoire t ON t.territoire_id = o.territoire_id
WHERE o.modalite_id IS NULL AND p.population > 0
UNION ALL
SELECT 'SURENDETTEMENT_POUR_100000',
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int,
       round(100000 * o.valeur / p.population),
       p.provisoire,
       'T',
       o.periode,
       o.periode_type
FROM stat.observation o
JOIN ref.indicateur i ON i.indicateur_id = o.indicateur_id
                     AND i.code = 'DOSSIERS_SURENDETTEMENT'
JOIN stat.structure_age p ON p.territoire_id = o.territoire_id AND p.periode = o.periode
JOIN ref.territoire t ON t.territoire_id = o.territoire_id
WHERE o.modalite_id IS NULL AND p.population > 0
UNION ALL
SELECT 'AIDE_LOGEMENT_MOYENNE',
       t.niveau,
       t.code,
       extract(year FROM m.periode)::int,
       round(m.valeur / f.valeur),
       false,
       'T',
       m.periode,
       m.periode_type
FROM stat.observation m
JOIN ref.indicateur mi ON mi.indicateur_id = m.indicateur_id
                      AND mi.code = 'MONTANT_AIDES_LOGEMENT'
JOIN stat.observation f
  ON f.territoire_id = m.territoire_id AND f.periode = m.periode AND f.modalite_id IS NULL
JOIN ref.indicateur fi ON fi.indicateur_id = f.indicateur_id
                      AND fi.code = 'FOYERS_AIDES_LOGEMENT'
JOIN ref.territoire t ON t.territoire_id = m.territoire_id
WHERE m.modalite_id IS NULL AND f.valeur > 0
UNION ALL
SELECT 'ECART_SALAIRE_FEMMES_HOMMES',
       t.niveau,
       t.code,
       extract(year FROM h.periode)::int,
       round(100 * (h.valeur - f.valeur) / h.valeur, 1),
       h.statut = 'PROVISOIRE' OR f.statut = 'PROVISOIRE',
       'T',
       h.periode,
       h.periode_type
FROM stat.observation h
JOIN ref.indicateur i ON i.indicateur_id = h.indicateur_id AND i.code = 'SALAIRE_NET_MOYEN'
JOIN stat.observation f
  ON f.indicateur_id = h.indicateur_id AND f.territoire_id = h.territoire_id
 AND f.periode = h.periode AND f.sexe = 'F'
 AND f.age_min IS NULL AND f.age_max IS NULL AND f.modalite_id IS NULL
JOIN ref.territoire t ON t.territoire_id = h.territoire_id
WHERE h.sexe = 'H' AND h.age_min IS NULL AND h.age_max IS NULL AND h.modalite_id IS NULL
  AND h.valeur > 0;

-- La vue lue par l'application ajoute ces indicateurs calculés (définition de la
-- migration 029, plus la dernière branche).
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
FROM stat.securite_derives
UNION ALL
-- Appli « Comment vivent les Français ? » : indicateurs calculés (migration 047).
SELECT indicateur, niveau, code, annee, valeur, provisoire, sexe, periode, periode_type
FROM stat.vivre_derives;
