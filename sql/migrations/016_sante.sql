-- Qui sont les Français ? Étape 3 : santé. Personnes prises en charge pour chaque grand
-- groupe de pathologies, traitement chronique ou épisode de soins (cartographie des
-- pathologies de l'Assurance maladie, par département de résidence).

INSERT INTO ref.source (code, producteur, libelle, url) VALUES
  ('CNAM_PATHO', 'Assurance maladie',
   'Cartographie des pathologies et des dépenses : effectifs de patients',
   'https://data.ameli.fr/explore/dataset/effectifs/');

-- Dans l'ordre des effectifs nationaux de 2024.
INSERT INTO ref.modalite (dimension, code, libelle) VALUES
  ('pathologie', 'AUCUNE', 'Ni pathologie, ni traitement chronique, ni hospitalisation'),
  ('pathologie', 'HOSPITALISATIONS', 'Hospitalisation ponctuelle (hors pathologies repérées)'),
  ('pathologie', 'RISQUE_VASCULAIRE', 'Traitement du risque vasculaire (hypertension, cholestérol)'),
  ('pathologie', 'PSYCHOTROPES', 'Traitement psychotrope (antidépresseur, anxiolytique, somnifère…)'),
  ('pathologie', 'CARDIO_NEUROVASCULAIRE', 'Maladies cardio-neurovasculaires'),
  ('pathologie', 'DIABETE', 'Diabète'),
  ('pathologie', 'RESPIRATOIRE', 'Maladies respiratoires chroniques (dont asthme)'),
  ('pathologie', 'CANCERS', 'Cancers'),
  ('pathologie', 'PSYCHIATRIQUE', 'Maladies psychiatriques'),
  ('pathologie', 'NEUROLOGIQUE', 'Maladies neurologiques (dont démences, Parkinson)'),
  ('pathologie', 'AUTRES_ALD', 'Autres affections de longue durée'),
  ('pathologie', 'INFLAMMATOIRE_RARE_VIH', 'Maladies inflammatoires, rares ou VIH'),
  ('pathologie', 'ANTALGIQUES', 'Traitement antalgique ou anti-inflammatoire au long cours'),
  ('pathologie', 'FOIE_PANCREAS', 'Maladies du foie ou du pancréas'),
  ('pathologie', 'INSUFFISANCE_RENALE', 'Insuffisance rénale chronique terminale (dialyse, greffe)');

INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id,
                            avertissement, comparabilite)
SELECT 'PATIENTS_PATHOLOGIE', 'Personnes prises en charge par groupe de pathologies',
       'Bénéficiaires de l''Assurance maladie (régime général et régimes rattachés) ayant '
       'eu au moins un soin remboursé dans l''année, selon les pathologies, traitements '
       'chroniques et épisodes de soins repérés dans leurs remboursements. Le total est '
       'l''ensemble des bénéficiaires pris en compte.',
       'personnes', 'effectif', s.source_id,
       'Une personne peut relever de plusieurs groupes : les parts ne s''additionnent pas. '
       'Seules les maladies ayant donné lieu à des soins remboursés sont repérées. '
       'Effectifs arrondis à la dizaine, au département de résidence.',
       'Série depuis 2015 ; les règles de repérage évoluent parfois d''une année à l''autre.'
FROM ref.source s
WHERE s.code = 'CNAM_PATHO';
