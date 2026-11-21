-- Appli 2, phase D : valeurs par tranche d'âge des indicateurs de la rubrique « besoins »
-- (niveau de vie et pauvreté des ménages dont la personne de référence a 18-29 ou
-- 30-39 ans), pour l'encadré 18-39 ans de la fiche département. api.serie ne garde que les
-- valeurs tous âges.
CREATE VIEW api.serie_age AS
SELECT i.code AS indicateur,
       t.niveau,
       t.code,
       extract(year FROM o.periode)::int AS annee,
       o.age_min,
       o.age_max,
       o.valeur,
       o.statut = 'PROVISOIRE' AS provisoire,
       o.periode,
       o.periode_type
FROM stat.observation o
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
WHERE i.rubrique = 'BESOINS'
  AND o.sexe = 'T'
  AND o.modalite_id IS NULL
  AND (o.age_min IS NOT NULL OR o.age_max IS NOT NULL);
