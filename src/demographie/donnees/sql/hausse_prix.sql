-- Hausse des prix à la consommation (France) entre une année de départ et la dernière
-- année complète, pour l'ensemble et chaque poste suivi : moyennes annuelles des indices
-- mensuels. Départ : %(debut)s, ou la première année complète si la série commence après.
WITH mois AS (
  SELECT 'ENSEMBLE' AS poste, 'Ensemble' AS libelle, 0 AS ordre, annee, valeur, provisoire
  FROM api.serie
  WHERE indicateur = 'IPC' AND niveau = 'FRANCE' AND code = 'FR' AND sexe = 'T'
  UNION ALL
  SELECT modalite, libelle, ordre, annee, valeur, provisoire
  FROM api.repartition
  WHERE indicateur = 'IPC' AND niveau = 'FRANCE' AND code = 'FR'
),
annuel AS (
  SELECT poste, libelle, ordre, annee, avg(valeur) AS valeur, count(*) AS nb_mois,
         bool_or(provisoire) AS provisoire
  FROM mois
  GROUP BY poste, libelle, ordre, annee
),
bornes AS (
  SELECT greatest(%(debut)s::int, min(annee)) AS debut, max(annee) AS fin
  FROM annuel
  WHERE poste = 'ENSEMBLE' AND nb_mois = 12
)
SELECT d.poste, d.libelle, b.debut, b.fin, f.provisoire,
       round(100 * (f.valeur / d.valeur - 1), 1) AS hausse
FROM bornes b
JOIN annuel d ON d.annee = b.debut AND d.nb_mois = 12
JOIN annuel f ON f.poste = d.poste AND f.annee = b.fin AND f.nb_mois = 12
WHERE b.fin > b.debut
ORDER BY d.ordre
