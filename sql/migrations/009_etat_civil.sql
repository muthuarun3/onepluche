-- Phase 2 : naissances et décès (état civil, INSEE, catalogue Melodi).

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, v.formule,
       'La dernière année est provisoire.',
       'Événements domiciliés : comptés au lieu de résidence de la mère ou du défunt.'
FROM ref.source s
CROSS JOIN (VALUES
  ('NAISSANCES', 'Naissances',
   'Nombre de naissances vivantes dans l''année, au domicile de la mère.',
   'personnes', 'flux', NULL),
  ('DECES', 'Décès',
   'Nombre de décès dans l''année, au domicile du défunt.',
   'personnes', 'flux', NULL),
  ('SOLDE_NATUREL', 'Solde naturel',
   'Naissances moins décès de l''année.',
   'personnes', 'flux', 'naissances − décès'),
  ('TAUX_NATALITE', 'Taux de natalité',
   'Naissances de l''année pour 1 000 habitants (population moyenne de l''année).',
   'pour_mille', 'taux', NULL),
  ('TAUX_MORTALITE', 'Taux de mortalité',
   'Décès de l''année pour 1 000 habitants (population moyenne de l''année).',
   'pour_mille', 'taux', NULL),
  ('ICF', 'Indicateur conjoncturel de fécondité',
   'Nombre moyen d''enfants par femme selon la fécondité par âge de l''année.',
   'ratio', 'ratio', NULL),
  ('ESPERANCE_VIE', 'Espérance de vie à la naissance',
   'Durée de vie moyenne d''une génération soumise toute sa vie à la mortalité par âge '
   'de l''année, par sexe.',
   'annees', 'ratio', NULL)
) AS v (code, libelle, definition, unite, nature, formule)
WHERE s.code = 'INSEE_EC';

-- Les séries servies par l'API couvrent maintenant toutes les observations
-- « tous âges », par sexe. La colonne sexe est ajoutée en fin de vue.
CREATE OR REPLACE VIEW api.serie AS
SELECT v.indicateur,
       t.niveau,
       t.code,
       extract(year FROM s.periode)::int AS annee,
       v.valeur,
       s.provisoire,
       'T'::char(1) AS sexe
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
       o.sexe
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
       'T'
FROM stat.observation n
JOIN ref.indicateur ni ON ni.indicateur_id = n.indicateur_id AND ni.code = 'NAISSANCES'
JOIN stat.observation d
  ON d.territoire_id = n.territoire_id AND d.periode = n.periode AND d.sexe = n.sexe
 AND d.age_min IS NULL AND d.age_max IS NULL AND d.modalite_id IS NULL
JOIN ref.indicateur di ON di.indicateur_id = d.indicateur_id AND di.code = 'DECES'
JOIN ref.territoire t ON t.territoire_id = n.territoire_id
WHERE n.sexe = 'T' AND n.age_min IS NULL AND n.age_max IS NULL AND n.modalite_id IS NULL;
