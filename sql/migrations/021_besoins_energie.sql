-- Appli 2, phase C : énergie des ménages. Dossier de conception de l'appli 2, étapes 5
-- et 6. Consommations et points de livraison du résidentiel (Agence ORE), diagnostics de
-- performance énergétique (ADEME), indice des prix à la consommation (INSEE, base 2025).
-- Électricité et gaz sont deux indicateurs chacun : additionner des points de livraison
-- d'électricité et de gaz compterait deux fois les logements raccordés aux deux.

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('ORE_CONSO', 'Agence ORE',
   'Consommation annuelle d''électricité et de gaz par département (gestionnaires de '
   'réseaux)',
   'https://opendata.agenceore.fr/explore/dataset/consommation-annuelle-d-electricite-et-gaz-par-departement/'),
  ('ADEME_DPE', 'ADEME',
   'Diagnostics de performance énergétique des logements existants (depuis juillet 2021)',
   'https://data.ademe.fr/datasets/dpe03existant'),
  ('INSEE_IPC', 'INSEE', 'Indice des prix à la consommation (base 2025)',
   'https://www.insee.fr/fr/metadonnees/source/serie/s1153');

INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('etiquette_dpe', 'A', 'Étiquette A'),
  ('etiquette_dpe', 'B', 'Étiquette B'),
  ('etiquette_dpe', 'C', 'Étiquette C'),
  ('etiquette_dpe', 'D', 'Étiquette D'),
  ('etiquette_dpe', 'E', 'Étiquette E'),
  ('etiquette_dpe', 'F', 'Étiquette F'),
  ('etiquette_dpe', 'G', 'Étiquette G'),
  ('poste_ipc', 'ENERGIE', 'Énergie'),
  ('poste_ipc', 'ELECTRICITE', 'Électricité'),
  ('poste_ipc', 'GAZ', 'Gaz'),
  ('poste_ipc', 'LOYERS', 'Loyers d''habitation'),
  ('poste_ipc', 'SANTE', 'Santé');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, angle,
                            borne_min, borne_max, seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       v.avertissement, NULL, 'BESOINS', v.theme, v.angle,
       v.borne_min, v.borne_max, v.seuil_variation::numeric
FROM (VALUES
  ('ORE_CONSO', 'CONSO_ELEC_RESID', 'Consommation d''électricité des logements',
   'Électricité consommée dans l''année par les clients résidentiels, tous '
   'gestionnaires de réseau du département.',
   'mwh', 'effectif', NULL,
   'Non corrigée du climat : un hiver froid l''augmente. Quelques petits sites sont '
   'couverts par le secret statistique.',
   'ENERGIE', NULL, NULL, NULL, NULL),
  ('ORE_CONSO', 'POINTS_ELEC_RESID', 'Logements raccordés à l''électricité',
   'Points de livraison résidentiels d''électricité (compteurs des logements).',
   'nombre', 'effectif', NULL, NULL, 'ENERGIE', NULL, NULL, NULL, NULL),
  ('ORE_CONSO', 'CONSO_GAZ_RESID', 'Consommation de gaz des logements',
   'Gaz naturel consommé dans l''année par les clients résidentiels raccordés au réseau.',
   'mwh', 'effectif', NULL,
   'Non corrigée du climat. Pas de réseau de gaz en Corse, en Lozère ni en outre-mer.',
   'ENERGIE', NULL, NULL, NULL, NULL),
  ('ORE_CONSO', 'POINTS_GAZ_RESID', 'Logements raccordés au gaz',
   'Points de livraison résidentiels de gaz naturel.',
   'nombre', 'effectif', NULL, NULL, 'ENERGIE', NULL, NULL, NULL, NULL),
  ('ORE_CONSO', 'CONSO_MOY_ELEC_LOGEMENT', 'Électricité consommée par logement raccordé',
   'Consommation annuelle moyenne d''électricité d''un logement raccordé.',
   'mwh', 'ratio', 'Consommation résidentielle / points de livraison résidentiels',
   'Non corrigée du climat ; plus élevée là où l''on se chauffe à l''électricité.',
   'ENERGIE', 'COUT', 0, 50, NULL),
  ('ORE_CONSO', 'CONSO_MOY_GAZ_LOGEMENT', 'Gaz consommé par logement raccordé',
   'Consommation annuelle moyenne de gaz d''un logement raccordé.',
   'mwh', 'ratio', 'Consommation résidentielle / points de livraison résidentiels',
   'Non corrigée du climat.',
   'ENERGIE', 'COUT', 0, 50, NULL),
  ('ADEME_DPE', 'DPE_ETABLIS', 'Diagnostics de performance énergétique établis',
   'DPE de logements existants établis dans l''année, par étiquette énergie (A à G).',
   'logements', 'flux', NULL,
   'Un DPE est obligatoire pour vendre ou louer : ces logements ne représentent pas '
   'tout le parc. 2021 commence en juillet ; l''année en cours est provisoire.',
   'ENERGIE', NULL, NULL, NULL, NULL),
  ('ADEME_DPE', 'PART_DPE_FG', 'Part des DPE classés F ou G',
   'Part des diagnostics de l''année classés F ou G (« passoires thermiques »).',
   'pourcentage', 'taux', '100 × DPE classés F ou G / DPE établis',
   'Parmi les logements vendus ou loués dans l''année, pas tout le parc.',
   'ENERGIE', 'MANQUE', 0, 100, NULL),
  ('INSEE_IPC', 'IPC', 'Indice des prix à la consommation',
   'Prix des biens et services consommés par les ménages, en France, par rapport à '
   'leur moyenne de 2025 (base 100). Ensemble et postes : énergie, électricité, gaz, '
   'loyers, santé.',
   'indice', 'prix', NULL,
   'Indice national, mensuel : il mesure l''évolution des prix, pas leur niveau.',
   'ENERGIE', 'COUT', 20, 300, NULL)
) AS v (source, code, libelle, definition, unite, nature, formule, avertissement, theme,
        angle, borne_min, borne_max, seuil_variation)
JOIN ref.source s ON s.code = v.source;

-- Les indicateurs calculés de l'appli 2 gagnent les consommations moyennes et la part
-- des DPE F ou G.
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
WHERE tot.modalite_id IS NULL AND tot.valeur > 0 AND fg.valeur IS NOT NULL;
