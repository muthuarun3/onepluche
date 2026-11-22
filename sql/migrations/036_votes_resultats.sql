-- Appli « Que pensent et votent les Français ? », PR V2 : résultats des élections.
-- Dossier de conception de l'appli, étapes 5 et 6 (validées le 22/11/2026).
--
-- Huit indicateurs lus dans les données agrégées du ministère de l'Intérieur, datés du
-- jour du tour (période SCRUTIN, migration 032). La participation n'a pas de modalité :
-- le jour suffit à reconnaître le scrutin (ref.scrutin.jour est unique). Les voix sont
-- ventilées par choix (candidat, liste ou nuance d'un scrutin, ref.choix_scrutin).
-- Avant 2014, blancs et nuls étaient comptés ensemble : BLANCS_ET_NULS existe pour tous
-- les tours, BLANCS et NULS seulement depuis.
-- Un résultat définitif ne bouge plus : toute modification d'une valeur publiée attend
-- une validation (seuil de variation nul).

-- La contrainte de la migration 017 n'admettait pas un seuil nul : elle accepte 0.
ALTER TABLE ref.indicateur DROP CONSTRAINT indicateur_seuil_variation_check,
  ADD CONSTRAINT indicateur_seuil_variation_check
      CHECK (seuil_variation >= 0 AND seuil_variation < 1);

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, comparabilite, rubrique, theme, borne_min,
                            seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, 'effectif', s.source_id, NULL,
       v.avertissement, v.comparabilite, 'VOTES', v.theme, 0, 0
FROM (VALUES
  ('INSCRITS', 'Inscrits', 'Électeurs inscrits sur les listes électorales du territoire.',
   'personnes', 'PARTICIPATION', NULL,
   'Au second tour des législatives et des municipales, seulement là où un second tour a eu lieu.'),
  ('VOTANTS', 'Votants', 'Inscrits qui ont voté, y compris blanc ou nul.',
   'personnes', 'PARTICIPATION', NULL,
   'Au second tour des législatives et des municipales, seulement là où un second tour a eu lieu.'),
  ('ABSTENTIONS', 'Abstentions', 'Inscrits qui n''ont pas voté.',
   'personnes', 'PARTICIPATION', NULL,
   'Au second tour des législatives et des municipales, seulement là où un second tour a eu lieu.'),
  ('BLANCS', 'Votes blancs', 'Bulletins blancs, comptés à part depuis la loi du 21 février 2014.',
   'nombre', 'PARTICIPATION', 'Avant 2014, les votes blancs étaient comptés avec les nuls.',
   'Depuis 2014 seulement ; avant, voir « blancs et nuls ».'),
  ('NULS', 'Votes nuls', 'Bulletins nuls, comptés à part des blancs depuis 2014.',
   'nombre', 'PARTICIPATION', 'Avant 2014, les votes blancs étaient comptés avec les nuls.',
   'Depuis 2014 seulement ; avant, voir « blancs et nuls ».'),
  ('BLANCS_ET_NULS', 'Votes blancs et nuls', 'Bulletins blancs et bulletins nuls ensemble.',
   'nombre', 'PARTICIPATION', NULL,
   'Comparable sur toute la période, avant et après la loi de 2014 sur le vote blanc.'),
  ('EXPRIMES', 'Suffrages exprimés', 'Votants moins les bulletins blancs et nuls : la base des pourcentages officiels des résultats.',
   'nombre', 'RESULTATS', NULL, NULL),
  ('VOIX', 'Voix', 'Voix obtenues par un candidat (présidentielle), une liste (européennes) ou l''ensemble des candidats d''une même nuance du ministère de l''Intérieur (législatives).',
   'nombre', 'RESULTATS',
   'Libellés officiels tels quels. Aux législatives, la nuance est attribuée par le ministère de l''Intérieur à chaque candidat.',
   'Un choix n''existe que pour son scrutin.')
) AS v (code, libelle, definition, unite, theme, avertissement, comparabilite)
CROSS JOIN ref.source s
WHERE s.code = 'MI_ELECTIONS';

-- Participation par scrutin et territoire, avec les taux officiels.
CREATE VIEW api.participation AS
WITH p AS (
  SELECT o.territoire_id, o.periode,
         max(o.valeur) FILTER (WHERE i.code = 'INSCRITS')       AS inscrits,
         max(o.valeur) FILTER (WHERE i.code = 'VOTANTS')        AS votants,
         max(o.valeur) FILTER (WHERE i.code = 'ABSTENTIONS')    AS abstentions,
         max(o.valeur) FILTER (WHERE i.code = 'BLANCS')         AS blancs,
         max(o.valeur) FILTER (WHERE i.code = 'NULS')           AS nuls,
         max(o.valeur) FILTER (WHERE i.code = 'BLANCS_ET_NULS') AS blancs_et_nuls,
         max(o.valeur) FILTER (WHERE i.code = 'EXPRIMES')       AS exprimes
  FROM stat.observation o
  JOIN ref.indicateur i USING (indicateur_id)
  WHERE i.rubrique = 'VOTES' AND o.modalite_id IS NULL AND o.periode_type = 'SCRUTIN'
  GROUP BY o.territoire_id, o.periode
)
SELECT m.code AS scrutin, m.libelle AS scrutin_libelle, s.election, s.annee, s.tour, s.jour,
       t.niveau, t.code,
       p.inscrits, p.votants, p.abstentions, p.blancs, p.nuls, p.blancs_et_nuls, p.exprimes,
       round(100 * p.abstentions / nullif(p.inscrits, 0), 2)    AS taux_abstention,
       round(100 * p.votants / nullif(p.inscrits, 0), 2)        AS taux_participation,
       round(100 * p.blancs / nullif(p.votants, 0), 2)          AS part_blancs_votants,
       round(100 * p.blancs_et_nuls / nullif(p.votants, 0), 2)  AS part_blancs_nuls_votants
FROM p
JOIN ref.scrutin s ON s.jour = p.periode
JOIN ref.modalite m ON m.modalite_id = s.modalite_id
JOIN ref.territoire t ON t.territoire_id = p.territoire_id;

-- Voix de chaque choix, avec la part des exprimés (le pourcentage officiel).
CREATE VIEW api.resultat AS
SELECT ms.code AS scrutin, t.niveau, t.code, mc.code AS choix, mc.libelle,
       c.panneau, c.nuance, o.valeur AS voix,
       round(100 * o.valeur / nullif(e.valeur, 0), 2) AS part_exprimes
FROM stat.observation o
JOIN ref.indicateur i ON i.indicateur_id = o.indicateur_id AND i.code = 'VOIX'
JOIN ref.choix_scrutin c ON c.modalite_id = o.modalite_id
JOIN ref.modalite mc ON mc.modalite_id = c.modalite_id
JOIN ref.modalite ms ON ms.modalite_id = c.scrutin_id
JOIN ref.territoire t ON t.territoire_id = o.territoire_id
LEFT JOIN ref.indicateur ie ON ie.code = 'EXPRIMES'
LEFT JOIN stat.observation e
  ON e.indicateur_id = ie.indicateur_id AND e.territoire_id = o.territoire_id
 AND e.periode = o.periode AND e.modalite_id IS NULL;

GRANT SELECT ON api.participation, api.resultat TO demo_lecture;
