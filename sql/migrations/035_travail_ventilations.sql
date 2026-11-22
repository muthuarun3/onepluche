-- Appli « Comment travaillent les Français ? », PR T3 : les ventilations (sexe, âge,
-- secteur, famille de métiers…) des indicateurs, que api.serie ne montre pas (elle ne
-- garde que les totaux). Une ligne par observation ventilée, avec sa période exacte.
-- Dossier de conception de l'appli travail, étape 8.

CREATE VIEW api.ventilation AS
SELECT i.code AS indicateur,
       t.niveau,
       t.code,
       o.periode,
       o.periode_type,
       extract(year FROM o.periode)::int AS annee,
       o.sexe,
       o.age_min,
       o.age_max,
       m.dimension,
       m.code AS modalite,
       m.libelle,
       o.valeur,
       o.statut = 'PROVISOIRE' AS provisoire
FROM stat.observation o
JOIN ref.indicateur i USING (indicateur_id)
JOIN ref.territoire t USING (territoire_id)
LEFT JOIN ref.modalite m USING (modalite_id)
WHERE o.sexe <> 'T' OR o.age_min IS NOT NULL OR o.age_max IS NOT NULL
   OR o.modalite_id IS NOT NULL;

GRANT SELECT ON api.ventilation TO demo_lecture;
