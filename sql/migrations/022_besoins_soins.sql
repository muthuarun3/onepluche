-- Appli 2, phase C : accès aux soins. Dossier de conception de l'appli 2, étapes 5 et 6.
-- Accessibilité potentielle localisée aux médecins généralistes (DREES), patients en
-- affection longue durée sans médecin traitant (Assurance maladie), équipements de santé
-- de la base permanente des équipements (INSEE), rapportés à la population.
-- Un indicateur par type d'équipement : un total « tous équipements de santé » mêlerait
-- pharmacies, urgences et cabinets.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('DREES_APL', 'DREES',
   'Accessibilité potentielle localisée (APL) aux médecins généralistes, par commune',
   'https://data.drees.solidarites-sante.gouv.fr/explore/dataset/530_l-accessibilite-potentielle-localisee-apl/'),
  ('CNAM_ACCES', 'Assurance maladie',
   'Observatoire de l''accès aux soins : patients en affection longue durée sans médecin '
   'traitant',
   'https://data.ameli.fr/explore/dataset/patients-longueduree-annuelle/'),
  ('INSEE_BPE', 'INSEE', 'Base permanente des équipements (BPE)',
   'https://www.insee.fr/fr/metadonnees/source/serie/s1161');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, NULL, 'BESOINS', 'SOINS', v.angle,
       v.borne_min, v.borne_max, v.seuil_variation::numeric
FROM (VALUES
  ('DREES_APL', 'APL_MG', 'Accès aux médecins généralistes',
   'Consultations de médecine générale accessibles par habitant et par an, compte tenu '
   'des médecins de 65 ans ou moins de la commune et des communes voisines, de leur '
   'activité et de l''âge des habitants (accessibilité potentielle localisée).',
   'consultations_hab', 'ratio',
   'Moyenne des communes pondérée par leur population standardisée (méthode DREES)',
   'Hors Mayotte. Médecins libéraux et salariés des centres de santé ; les médecins '
   'hospitaliers ne sont pas comptés.',
   'ACCES', 0, 20, 0.15),
  ('DREES_APL', 'PART_POP_APL_MG_FAIBLE',
   'Habitants mal desservis en médecins généralistes',
   'Part des habitants vivant dans une commune où l''on accède à moins de 2,5 '
   'consultations de médecine générale par habitant et par an (seuil des zones '
   'sous-denses).',
   'pourcentage', 'taux',
   '100 × population des communes sous 2,5 consultations / population totale',
   'Hors Mayotte. Calcul On épluche à partir des valeurs communales de la DREES.',
   'MANQUE', 0, 100, NULL),
  ('CNAM_ACCES', 'ALD_SANS_MT',
   'Malades chroniques sans médecin traitant',
   'Part des patients en affection longue durée (diabète, cancer, insuffisance '
   'cardiaque…) qui n''ont pas déclaré de médecin traitant.',
   'pourcentage', 'taux', NULL, NULL,
   'MANQUE', 0, 100, NULL),
  ('INSEE_BPE', 'LIEUX_MG', 'Médecins généralistes',
   'Médecins généralistes libéraux recensés par la base permanente des équipements, '
   'comptés à chaque adresse où ils exercent.',
   'nombre', 'effectif', NULL,
   'Un médecin qui consulte à deux adresses compte deux fois.',
   NULL, NULL, NULL, NULL),
  ('INSEE_BPE', 'PHARMACIES', 'Pharmacies',
   'Officines de pharmacie ouvertes au public.',
   'nombre', 'effectif', NULL, NULL,
   NULL, NULL, NULL, NULL),
  ('INSEE_BPE', 'URGENCES', 'Services d''urgences',
   'Services d''accueil des urgences des établissements de santé (adultes et enfants).',
   'nombre', 'effectif', NULL, NULL,
   'ACCES', NULL, NULL, NULL),
  ('INSEE_BPE', 'MAISONS_SANTE', 'Maisons de santé',
   'Maisons de santé pluriprofessionnelles : médecins et autres soignants libéraux '
   'regroupés autour d''un projet de soins commun.',
   'nombre', 'effectif', NULL, NULL,
   'ACCES', NULL, NULL, NULL),
  ('INSEE_BPE', 'MG_10000', 'Médecins généralistes pour 10 000 habitants',
   'Lieux d''exercice de médecins généralistes pour 10 000 habitants.',
   'pour_10000', 'ratio',
   '10 000 × médecins généralistes (BPE) / population estimée au 1er janvier',
   'Un médecin qui consulte à deux adresses compte deux fois. Calcul On épluche.',
   'ACCES', 0, 50, NULL),
  ('INSEE_BPE', 'PHARMACIES_10000', 'Pharmacies pour 10 000 habitants',
   'Pharmacies pour 10 000 habitants.',
   'pour_10000', 'ratio',
   '10 000 × pharmacies (BPE) / population estimée au 1er janvier',
   'Calcul On épluche.',
   'ACCES', 0, 20, NULL)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement, angle,
        borne_min, borne_max, seuil_variation)
JOIN ref.source s ON s.code = v.source;

-- Les indicateurs calculés de l'appli 2 gagnent les densités de médecins généralistes et
-- de pharmacies (population estimée la plus récente au 1er janvier de l'année ou avant).
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
    ('PART_CHAUFFAGE_FIOUL', 'RESIDENCES_PRINC_CHAUFFAGE', 'combustible', 'FIOUL')
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
WHERE pop.valeur > 0;
