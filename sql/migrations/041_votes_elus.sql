-- Appli « Que pensent et votent les Français ? », PR V3 : portrait des élus.
-- Dossier de conception de l'appli, étapes 5 et 6 (validées le 22/11/2026).
--
-- Un indicateur par mandat (maires, conseillers départementaux, députés, sénateurs), lu
-- dans le Répertoire national des élus : élus en fonction le mois de la mise à jour du
-- fichier, au total, par sexe, par tranche d'âge et par groupe socioprofessionnel
-- (dimension « pcs », les huit groupes de la population). Un indicateur par mandat, et
-- non un seul ventilé par mandat, parce qu'une observation n'a qu'une modalité et que
-- le groupe socioprofessionnel l'occupe déjà. L'âge médian est ventilé par mandat.
-- Aucun nom n'est enregistré.

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, borne_min)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, NULL,
       v.avertissement, v.comparabilite, 'VOTES', 'ELUS', 0
FROM (VALUES
  ('ELUS_MAIRES', 'Maires', 'Maires en fonction, d''après le Répertoire national des élus.',
   'personnes', 'effectif', NULL,
   'Compté le mois de la mise à jour du Répertoire ; les municipales de mars 2026 ont renouvelé les maires.'),
  ('ELUS_CONSEILLERS_DEP', 'Conseillers départementaux',
   'Conseillers départementaux en fonction, d''après le Répertoire national des élus.',
   'personnes', 'effectif',
   'Paris, la Corse, la Martinique et la Guyane n''ont pas de conseil départemental : leurs élus siègent dans des assemblées à statut particulier, non comptées ici.',
   'Compté le mois de la mise à jour du Répertoire.'),
  ('ELUS_DEPUTES', 'Députés',
   'Députés en fonction, rattachés au département de leur circonscription.',
   'personnes', 'effectif',
   'Un siège vacant n''est pas compté. Les députés des Français de l''étranger sont un territoire à part.',
   'Compté le mois de la mise à jour du Répertoire.'),
  ('ELUS_SENATEURS', 'Sénateurs',
   'Sénateurs en fonction, rattachés au département qu''ils représentent.',
   'personnes', 'effectif',
   'Les sénateurs des Français de l''étranger sont un territoire à part.',
   'Compté le mois de la mise à jour du Répertoire.'),
  ('AGE_MEDIAN_ELUS', 'Âge médian des élus',
   'Âge qui partage les élus d''un mandat en deux moitiés, calculé à la date du fichier.',
   'annees', 'ratio', NULL,
   'Compté le mois de la mise à jour du Répertoire.')
) AS v (code, libelle, definition, unite, nature, avertissement, comparabilite)
CROSS JOIN ref.source s
WHERE s.code = 'MI_RNE';

-- Portrait des élus par mandat, territoire et mois : effectif, femmes, moins de 40 ans,
-- âge médian, et les parts correspondantes.
CREATE VIEW api.elus AS
WITH mandats (indicateur, mandat) AS (
  VALUES ('ELUS_MAIRES', 'MAIRE'), ('ELUS_CONSEILLERS_DEP', 'CONSEILLER_DEP'),
         ('ELUS_DEPUTES', 'DEPUTE'), ('ELUS_SENATEURS', 'SENATEUR')
),
e AS (
  SELECT mn.mandat, o.territoire_id, o.periode,
         max(o.valeur) FILTER (WHERE o.sexe = 'T' AND o.age_min IS NULL
                                 AND o.modalite_id IS NULL)              AS elus,
         max(o.valeur) FILTER (WHERE o.sexe = 'F' AND o.modalite_id IS NULL) AS femmes,
         coalesce(max(o.valeur) FILTER (WHERE o.age_min = 18 AND o.age_max = 39), 0)
                                                                         AS moins_de_40_ans
  FROM stat.observation o
  JOIN ref.indicateur i USING (indicateur_id)
  JOIN mandats mn ON mn.indicateur = i.code
  GROUP BY mn.mandat, o.territoire_id, o.periode
)
SELECT e.mandat, m.libelle AS mandat_libelle, t.niveau, t.code, e.periode,
       e.elus, coalesce(e.femmes, 0) AS femmes, e.moins_de_40_ans, a.valeur AS age_median,
       round(100 * coalesce(e.femmes, 0) / nullif(e.elus, 0), 1)  AS part_femmes,
       round(100 * e.moins_de_40_ans / nullif(e.elus, 0), 1)      AS part_moins_de_40_ans
FROM e
JOIN ref.modalite m ON m.dimension = 'mandat' AND m.code = e.mandat
JOIN ref.territoire t ON t.territoire_id = e.territoire_id
LEFT JOIN ref.indicateur ia ON ia.code = 'AGE_MEDIAN_ELUS'
LEFT JOIN stat.observation a
  ON a.indicateur_id = ia.indicateur_id AND a.territoire_id = e.territoire_id
 AND a.periode = e.periode AND a.modalite_id = m.modalite_id
WHERE e.elus IS NOT NULL;

GRANT SELECT ON api.elus TO demo_lecture;
