-- Appli 3 « Comment vivent les Français ? » (rubrique /vivre), phase A1 : catalogue,
-- revenus détaillés Filosofi et salaires du secteur privé. Dossier de conception de
-- l'appli 3, étapes 3 et 5 (validées le 22/11/2026).

-- Rubrique VIVRE (ordre 3, réservé) et ses sept thèmes (dossier, étape 1).
INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire, avec_angles)
VALUES ('VIVRE', 'Comment vivent les Français ?', '/vivre', 3, true, false);

INSERT INTO ref.theme (rubrique, code, libelle, ordre) VALUES
  ('VIVRE', 'REVENUS', 'Revenus', 1),
  ('VIVRE', 'POUVOIR_ACHAT', 'Pouvoir d''achat', 2),
  ('VIVRE', 'INEGALITES', 'Inégalités', 3),
  ('VIVRE', 'EPARGNE', 'Épargne et dettes', 4),
  ('VIVRE', 'PATRIMOINE', 'Patrimoine', 5),
  ('VIVRE', 'AIDES_LOGEMENT', 'Aides au logement', 6),
  ('VIVRE', 'RETRAITES', 'Retraites', 7);

-- Un indicateur est importé une seule fois, dans sa rubrique d'origine, et peut s'afficher
-- dans d'autres rubriques (dossier de l'appli 3, étape 3). Exemple : le niveau de vie
-- médian de l'appli 2 apparaît aussi dans le thème Revenus de l'appli 3.
CREATE TABLE ref.indicateur_affichage (
  indicateur_id smallint NOT NULL REFERENCES ref.indicateur,
  rubrique      text     NOT NULL REFERENCES ref.rubrique,
  theme         text,
  ordre         smallint NOT NULL DEFAULT 0,
  PRIMARY KEY (indicateur_id, rubrique),
  FOREIGN KEY (rubrique, theme) REFERENCES ref.theme (rubrique, code)
);

GRANT SELECT ON ref.indicateur_affichage TO demo_import;

CREATE VIEW api.indicateur_affichage AS
SELECT i.code AS indicateur, a.rubrique, a.theme, a.ordre
FROM ref.indicateur_affichage a
JOIN ref.indicateur i USING (indicateur_id);

GRANT SELECT ON api.indicateur_affichage TO demo_lecture;

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('INSEE_BTS', 'INSEE',
   'Base Tous salariés : salaires du secteur privé par département',
   'https://www.insee.fr/fr/metadonnees/source/serie/s1163');

-- BTS regroupe cadres et chefs d'entreprise salariés (PCS-ESE 1 à 3).
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('pcs', 'CADRES_DIRIGEANTS',
   'Cadres, professions intellectuelles supérieures et chefs d''entreprise salariés');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id, formule,
                            avertissement, rubrique, theme, borne_min, borne_max,
                            seuil_variation)
SELECT v.code, v.libelle, v.definition, v.unite, v.nature, s.source_id, NULL,
       v.avertissement, 'VIVRE', v.theme, v.borne_min, v.borne_max, v.seuil
FROM (VALUES
  -- Filosofi : distribution du niveau de vie.
  ('INSEE_FILOSOFI', 'NIVEAU_VIE_D1', 'Niveau de vie des 10 % les plus modestes (1er décile)',
   'Niveau de vie annuel sous lequel se situent les 10 % des personnes les plus modestes. '
   'Le niveau de vie est le revenu disponible du ménage divisé par son nombre d''unités de '
   'consommation.',
   'euros', 'ratio', NULL, 'INEGALITES', 3000, 40000, 0.15),
  ('INSEE_FILOSOFI', 'NIVEAU_VIE_D9', 'Niveau de vie des 10 % les plus aisés (9e décile)',
   'Niveau de vie annuel au-dessus duquel se situent les 10 % des personnes les plus aisées.',
   'euros', 'ratio', NULL, 'INEGALITES', 15000, 150000, 0.15),
  ('INSEE_FILOSOFI', 'RAPPORT_D9_D1', 'Rapport entre les plus aisés et les plus modestes (D9/D1)',
   'Niveau de vie du 9e décile divisé par celui du 1er décile : les 10 % les plus aisés '
   'ont au moins ce multiple du niveau de vie des 10 % les plus modestes.',
   'ratio', 'ratio', NULL, 'INEGALITES', 1.5, 10, 0.15),
  ('INSEE_FILOSOFI', 'INDICE_GINI', 'Indice de Gini du niveau de vie',
   'Mesure des inégalités de niveau de vie, de 0 (tous égaux) à 1 (une seule personne '
   'détient tout).',
   'ratio', 'ratio', NULL, 'INEGALITES', 0.15, 0.6, 0.15),
  ('INSEE_FILOSOFI', 'RAPPORT_S80_S20', 'Rapport des niveaux de vie des 20 % extrêmes (S80/S20)',
   'Somme des niveaux de vie des 20 % les plus aisés divisée par celle des 20 % les plus '
   'modestes.',
   'ratio', 'ratio', NULL, 'INEGALITES', 1.5, 15, 0.15),
  -- Filosofi : d'où vient le revenu disponible (en % du revenu disponible).
  ('INSEE_FILOSOFI', 'PART_REVENUS_ACTIVITE', 'Part des revenus d''activité dans le revenu',
   'Salaires, traitements, indemnités de chômage et revenus des indépendants, en % du '
   'revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'REVENUS', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_SALAIRES', 'Part des salaires dans le revenu',
   'Salaires et traitements, en % du revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'REVENUS', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_CHOMAGE', 'Part des indemnités de chômage dans le revenu',
   'Indemnités de chômage, en % du revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'REVENUS', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_REVENUS_PATRIMOINE', 'Part des revenus du patrimoine dans le revenu',
   'Revenus du patrimoine (intérêts, dividendes, loyers perçus…) et autres revenus, en % '
   'du revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'REVENUS', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_PRESTATIONS', 'Part des prestations sociales dans le revenu',
   'Prestations familiales, aides au logement et minima sociaux, en % du revenu disponible '
   'des ménages.',
   'pourcentage', 'taux', NULL, 'REVENUS', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_IMPOTS', 'Poids des impôts directs dans le revenu',
   'Impôts directs (impôt sur le revenu, taxe d''habitation, CSG et CRDS sur les revenus '
   'du patrimoine) retirés du revenu, en % du revenu disponible. L''INSEE les publie en '
   'négatif ; On épluche les affiche en positif.',
   'pourcentage', 'taux', NULL, 'REVENUS', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_MINIMA_SOCIAUX', 'Part des minima sociaux dans le revenu',
   'RSA, allocation aux adultes handicapés, minimum vieillesse et autres minima sociaux, '
   'en % du revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'INEGALITES', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_AIDES_LOGEMENT', 'Part des aides au logement dans le revenu',
   'Aides personnelles au logement (APL, ALF, ALS), en % du revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'AIDES_LOGEMENT', 0, 100, NULL),
  ('INSEE_FILOSOFI', 'PART_PENSIONS', 'Part des pensions et retraites dans le revenu',
   'Pensions, retraites et rentes, en % du revenu disponible des ménages.',
   'pourcentage', 'taux', NULL, 'RETRAITES', 0, 100, NULL),
  -- Base Tous salariés.
  ('INSEE_BTS', 'SALAIRE_NET_MOYEN', 'Salaire net mensuel moyen (secteur privé)',
   'Salaire net de prélèvements sociaux, en équivalent temps plein, par mois, des salariés '
   'du secteur privé travaillant dans le département. Par sexe, catégorie '
   'socioprofessionnelle et tranche d''âge.',
   'euros', 'ratio',
   'Secteur privé seulement, en équivalent temps plein : un temps partiel compte pour '
   'sa part d''une année complète. Un salaire moyen est tiré vers le haut par les hauts '
   'salaires.',
   'REVENUS', 1000, 9000, 0.15)
) AS v (source, code, libelle, definition, unite, nature, avertissement, theme, borne_min,
        borne_max, seuil)
JOIN ref.source s ON s.code = v.source;

UPDATE ref.indicateur
SET comparabilite = 'Un seul millésime (2023) est publié par département : pas d''évolution '
                    'locale. Champ : France métropolitaine et La Réunion.'
WHERE code IN ('NIVEAU_VIE_D1', 'NIVEAU_VIE_D9', 'RAPPORT_D9_D1', 'INDICE_GINI',
               'RAPPORT_S80_S20', 'PART_REVENUS_ACTIVITE', 'PART_SALAIRES', 'PART_CHOMAGE',
               'PART_REVENUS_PATRIMOINE', 'PART_PRESTATIONS', 'PART_IMPOTS',
               'PART_MINIMA_SOCIAUX', 'PART_AIDES_LOGEMENT', 'PART_PENSIONS');

-- Indicateurs des applis 1 et 2 affichés aussi dans l'appli 3 (dossier, étape 5).
INSERT INTO ref.indicateur_affichage (indicateur_id, rubrique, theme, ordre)
SELECT i.indicateur_id, 'VIVRE', v.theme, v.ordre
FROM (VALUES
  ('NIVEAU_VIE_MEDIAN', 'REVENUS', 1),
  ('TAUX_PAUVRETE', 'INEGALITES', 1),
  ('IPC', 'POUVOIR_ACHAT', 1),
  ('PENSIONNES', 'RETRAITES', 1),
  ('MIN_VIEILLESSE', 'RETRAITES', 2),
  ('TAUX_MIN_VIEILLESSE_60P', 'RETRAITES', 3)
) AS v (code, theme, ordre)
JOIN ref.indicateur i ON i.code = v.code;
