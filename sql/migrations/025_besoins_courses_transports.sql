-- Appli 2 : courses, carburant et transports (demande de Muthu du 21/11/2026).
-- Prix des carburants par département (stations, ministère de l'Économie), trajets
-- domicile-travail et voitures des ménages (recensement), dépense des ménages en
-- carburants (comptes nationaux) ; indice des prix de l'alimentation, des carburants et
-- des transports ; dépense moyenne par ménage et par mois pour l'alimentation, les
-- transports et les carburants (France). Aucune source publique ne donne de « panier
-- moyen » par département : la dépense alimentaire par ménage est nationale.

ALTER TABLE ref.indicateur DROP CONSTRAINT indicateur_unite_check;
ALTER TABLE ref.indicateur ADD CONSTRAINT indicateur_unite_check
  CHECK (unite IN ('personnes', 'pourcentage', 'pour_mille', 'ratio', 'annees',
                   'logements', 'nombre', 'euros', 'euros_m2', 'mwh', 'indice',
                   'consultations_hab', 'pour_10000', 'millions_euros', 'euros_litre'));

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('MINEFI_CARBURANTS', 'Ministère de l''Économie',
   'Prix des carburants déclarés par les stations-service (flux instantané)',
   'https://data.economie.gouv.fr/explore/dataset/prix-des-carburants-en-france-flux-instantane-v2/');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('mode_transport', 'AUCUN', 'Pas de transport (travail à domicile)'),
  ('mode_transport', 'MARCHE', 'Marche à pied'),
  ('mode_transport', 'VELO', 'Vélo'),
  ('mode_transport', 'DEUX_ROUES_MOTORISE', 'Deux-roues motorisé'),
  ('mode_transport', 'VOITURE', 'Voiture, camion, fourgonnette'),
  ('mode_transport', 'TRANSPORTS_COMMUN', 'Transports en commun'),
  ('voitures_menage', 'AUCUNE', 'Aucune voiture'),
  ('voitures_menage', 'UNE', 'Une voiture'),
  ('voitures_menage', 'DEUX_OU_PLUS', 'Deux voitures ou plus'),
  ('poste_ipc', 'ALIMENTATION', 'Alimentation'),
  ('poste_ipc', 'CARBURANTS', 'Carburants'),
  ('poste_ipc', 'TRANSPORTS', 'Transports');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, v.comparabilite, 'BESOINS', v.theme, v.angle,
       v.borne_min, v.borne_max, v.seuil_variation::numeric
FROM (VALUES
  ('MINEFI_CARBURANTS', 'PRIX_GAZOLE', 'Prix du gazole',
   'Prix moyen d''un litre de gazole dans les stations-service, le jour du relevé.',
   'euros_litre', 'prix', 'Moyenne simple des prix affichés par les stations',
   'Moyenne des stations ayant mis leur prix à jour dans les 7 jours, sans pondération '
   'par les volumes vendus. Un relevé par mois (le plus récent). Outre-mer non couvert '
   '(prix réglementés).', NULL, 'TRANSPORTS', 'COUT', 0.5, 5, 0.15),
  ('MINEFI_CARBURANTS', 'PRIX_SP95_E10', 'Prix du sans-plomb 95-E10',
   'Prix moyen d''un litre de sans-plomb 95-E10, l''essence la plus vendue, dans les '
   'stations-service, le jour du relevé.',
   'euros_litre', 'prix', 'Moyenne simple des prix affichés par les stations',
   'Moyenne des stations ayant mis leur prix à jour dans les 7 jours, sans pondération '
   'par les volumes vendus. Un relevé par mois (le plus récent). Outre-mer non couvert '
   '(prix réglementés).', NULL, 'TRANSPORTS', 'COUT', 0.5, 5, 0.15),
  ('INSEE_RP', 'ACTIFS_TRAJET', 'Actifs selon le moyen de transport pour aller travailler',
   'Actifs ayant un emploi, de 15 ans ou plus, selon le moyen de transport le plus '
   'souvent utilisé pour aller travailler.',
   'personnes', 'effectif', NULL, 'Hors Mayotte.',
   'Millésime = moyenne de 5 enquêtes annuelles : ne comparer que des millésimes séparés '
   'd''au moins 5 ans (ex. 2017 et 2023).', 'TRANSPORTS', NULL, NULL, NULL, NULL),
  ('INSEE_RP', 'MENAGES_VOITURES', 'Ménages selon le nombre de voitures',
   'Résidences principales selon le nombre de voitures dont dispose le ménage.',
   'logements', 'effectif', NULL, 'Hors Mayotte.',
   'Millésime = moyenne de 5 enquêtes annuelles : ne comparer que des millésimes séparés '
   'd''au moins 5 ans (ex. 2017 et 2023).', 'TRANSPORTS', NULL, NULL, NULL, NULL),
  ('INSEE_RP', 'PART_TRAJET_VOITURE', 'Actifs qui vont travailler en voiture',
   'Part des actifs ayant un emploi qui vont le plus souvent travailler en voiture, '
   'camion ou fourgonnette.',
   'pourcentage', 'taux', '100 × actifs allant travailler en voiture / actifs ayant un emploi',
   'Hors Mayotte.', NULL, 'TRANSPORTS', 'ACCES', 0, 100, NULL),
  ('INSEE_RP', 'PART_TRAJET_TRANSPORTS_COMMUN', 'Actifs qui vont travailler en transports en commun',
   'Part des actifs ayant un emploi qui vont le plus souvent travailler en transports en '
   'commun (bus, tramway, métro, train).',
   'pourcentage', 'taux',
   '100 × actifs allant travailler en transports en commun / actifs ayant un emploi',
   'Hors Mayotte.', NULL, 'TRANSPORTS', 'ACCES', 0, 100, NULL),
  ('INSEE_RP', 'PART_MENAGES_SANS_VOITURE', 'Ménages sans voiture',
   'Part des ménages qui ne disposent d''aucune voiture.',
   'pourcentage', 'taux', '100 × ménages sans voiture / ménages',
   'Hors Mayotte. En ville, ne pas avoir de voiture est souvent un choix ; ailleurs, '
   'c''est plus souvent une contrainte.', NULL, 'TRANSPORTS', 'MANQUE', 0, 100, NULL),
  ('INSEE_CNA', 'DEPENSE_CARBURANTS', 'Dépense des ménages en carburants',
   'Ce que les ménages résidant en France dépensent dans l''année en carburants et '
   'lubrifiants pour leurs véhicules, en millions d''euros courants.',
   'millions_euros', 'flux', NULL,
   'Comptes nationaux. Les trois dernières années sont provisoires.',
   NULL, 'TRANSPORTS', NULL, 0, NULL, NULL),
  ('INSEE_CNA', 'DEPENSE_MOIS_ALIMENTATION', 'Courses alimentaires par ménage et par mois',
   'Dépense moyenne d''un ménage pour l''alimentation et les boissons non alcoolisées '
   'achetées pour la maison, par mois (hors restaurants et cantines).',
   'euros', 'ratio',
   'Dépense des ménages en alimentation (comptes nationaux) / nombre de ménages / 12',
   'Moyenne de tous les ménages, France entière : aucune source publique ne donne de '
   'panier moyen par département. Calcul On épluche.', NULL, 'ALIMENTATION', 'COUT',
   0, NULL, NULL),
  ('INSEE_CNA', 'DEPENSE_MOIS_TRANSPORTS', 'Transports par ménage et par mois',
   'Dépense moyenne d''un ménage pour ses transports par mois : achat et entretien des '
   'véhicules, carburant, billets de train, d''avion et de transports en commun.',
   'euros', 'ratio',
   'Dépense des ménages en transports (comptes nationaux) / nombre de ménages / 12',
   'Moyenne de tous les ménages, France entière. Calcul On épluche.', NULL, 'TRANSPORTS',
   'COUT', 0, NULL, NULL),
  ('INSEE_CNA', 'DEPENSE_MOIS_CARBURANTS', 'Carburant par ménage et par mois',
   'Dépense moyenne d''un ménage en carburant pour ses véhicules, par mois.',
   'euros', 'ratio',
   'Dépense des ménages en carburants (comptes nationaux) / nombre de ménages / 12',
   'Moyenne de tous les ménages, y compris ceux sans voiture, France entière. Calcul On '
   'épluche.', NULL, 'TRANSPORTS', 'COUT', 0, NULL, NULL)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement,
        comparabilite, theme, angle, borne_min, borne_max, seuil_variation)
JOIN ref.source s ON s.code = v.source;

-- Les indicateurs calculés de l'appli 2 gagnent les parts de trajets et de ménages sans
-- voiture, et les dépenses par ménage et par mois.
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
    ('PART_CHAUFFAGE_FIOUL', 'RESIDENCES_PRINC_CHAUFFAGE', 'combustible', 'FIOUL'),
    ('PART_TRAJET_VOITURE', 'ACTIFS_TRAJET', 'mode_transport', 'VOITURE'),
    ('PART_TRAJET_TRANSPORTS_COMMUN', 'ACTIFS_TRAJET', 'mode_transport', 'TRANSPORTS_COMMUN'),
    ('PART_MENAGES_SANS_VOITURE', 'MENAGES_VOITURES', 'voitures_menage', 'AUCUNE')
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
WHERE p.modalite_id IS NULL AND p.sexe = 'T' AND p.age_min IS NULL AND p.age_max IS NULL
UNION ALL
SELECT v.indicateur, t.niveau, t.code, extract(year FROM c.periode)::int,
       round(c.valeur / nullif(p.valeur, 0), 2), false, 'T'::char(1), c.periode,
       c.periode_type
FROM (VALUES ('CONSO_MOY_ELEC_LOGEMENT', 'CONSO_ELEC_RESID', 'POINTS_ELEC_RESID'),
             ('CONSO_MOY_GAZ_LOGEMENT', 'CONSO_GAZ_RESID', 'POINTS_GAZ_RESID'))
     AS v (indicateur, conso, points)
JOIN ref.indicateur ci ON ci.code = v.conso
JOIN ref.indicateur pi ON pi.code = v.points
JOIN stat.observation c ON c.indicateur_id = ci.indicateur_id AND c.modalite_id IS NULL
JOIN stat.observation p
  ON p.indicateur_id = pi.indicateur_id AND p.territoire_id = c.territoire_id
 AND p.periode = c.periode AND p.modalite_id IS NULL
JOIN ref.territoire t ON t.territoire_id = c.territoire_id
WHERE p.valeur > 0
UNION ALL
SELECT 'PART_DPE_FG', t.niveau, t.code, extract(year FROM tot.periode)::int,
       round(100 * fg.valeur / tot.valeur, 1), tot.statut = 'PROVISOIRE', 'T'::char(1),
       tot.periode, tot.periode_type
FROM stat.observation tot
JOIN ref.indicateur i ON i.indicateur_id = tot.indicateur_id AND i.code = 'DPE_ETABLIS'
CROSS JOIN LATERAL (
  SELECT sum(o.valeur) AS valeur
  FROM stat.observation o
  JOIN ref.modalite m ON m.modalite_id = o.modalite_id
  WHERE o.indicateur_id = tot.indicateur_id AND o.territoire_id = tot.territoire_id
    AND o.periode = tot.periode AND m.dimension = 'etiquette_dpe' AND m.code IN ('F', 'G')
) fg
JOIN ref.territoire t ON t.territoire_id = tot.territoire_id
WHERE tot.modalite_id IS NULL AND tot.valeur > 0 AND fg.valeur IS NOT NULL
UNION ALL
SELECT v.indicateur, t.niveau, t.code, extract(year FROM e.periode)::int,
       round(10000 * e.valeur / pop.valeur, 1), pop.statut = 'PROVISOIRE', 'T'::char(1),
       e.periode, e.periode_type
FROM (VALUES ('MG_10000', 'LIEUX_MG'), ('PHARMACIES_10000', 'PHARMACIES'))
     AS v (indicateur, equipement)
JOIN ref.indicateur ei ON ei.code = v.equipement
JOIN stat.observation e
  ON e.indicateur_id = ei.indicateur_id AND e.modalite_id IS NULL AND e.sexe = 'T'
 AND e.age_min IS NULL AND e.age_max IS NULL
JOIN ref.territoire t ON t.territoire_id = e.territoire_id
CROSS JOIN LATERAL (
  SELECT o.valeur, o.statut
  FROM stat.observation o
  JOIN ref.indicateur pi ON pi.indicateur_id = o.indicateur_id
  WHERE pi.code = 'POP' AND o.territoire_id = e.territoire_id AND o.periode <= e.periode
    AND o.sexe = 'T' AND o.age_min IS NULL AND o.age_max IS NULL AND o.modalite_id IS NULL
  ORDER BY o.periode DESC
  LIMIT 1
) pop
WHERE pop.valeur > 0
UNION ALL
-- Dépense moyenne par ménage et par mois (France) : dépense annuelle des comptes
-- nationaux / nombre de ménages (résidences principales du dernier recensement publié
-- au plus tard cette année-là) / 12.
SELECT v.indicateur, t.niveau, t.code, extract(year FROM d.periode)::int,
       round(1000000 * d.valeur / m.valeur / 12), d.statut = 'PROVISOIRE', 'T'::char(1),
       d.periode, d.periode_type
FROM (VALUES ('DEPENSE_MOIS_ALIMENTATION', 'DEPENSE_CONSO_MENAGES', 'ALIMENTATION'),
             ('DEPENSE_MOIS_TRANSPORTS', 'DEPENSE_CONSO_MENAGES', 'TRANSPORTS'),
             ('DEPENSE_MOIS_CARBURANTS', 'DEPENSE_CARBURANTS', NULL))
     AS v (indicateur, base, poste)
JOIN ref.indicateur di ON di.code = v.base
LEFT JOIN ref.modalite pm ON pm.dimension = 'poste_conso' AND pm.code = v.poste
JOIN stat.observation d
  ON d.indicateur_id = di.indicateur_id
 AND d.modalite_id IS NOT DISTINCT FROM pm.modalite_id
 AND d.sexe = 'T' AND d.age_min IS NULL AND d.age_max IS NULL
JOIN ref.territoire t ON t.territoire_id = d.territoire_id
CROSS JOIN LATERAL (
  SELECT o.valeur
  FROM stat.observation o
  JOIN ref.indicateur ri ON ri.indicateur_id = o.indicateur_id
  WHERE ri.code = 'RESIDENCES_PRINC' AND o.territoire_id = d.territoire_id
    AND o.periode <= d.periode AND o.sexe = 'T' AND o.modalite_id IS NULL
    AND o.age_min IS NULL AND o.age_max IS NULL
  ORDER BY o.periode DESC
  LIMIT 1
) m
WHERE m.valeur > 0 AND (v.poste IS NULL OR pm.modalite_id IS NOT NULL);
