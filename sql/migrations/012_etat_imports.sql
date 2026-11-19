-- État des imports par source et par fichier, pour la page « Sources » et l'API.
CREATE VIEW api.etat_import AS
SELECT s.code      AS source,
       s.producteur,
       s.libelle   AS source_libelle,
       s.url       AS source_url,
       s.licence,
       d.fichier_nom,
       d.statut    AS dernier_statut,
       d.debut     AS dernier_essai,
       p.fin       AS derniere_publication,
       p.millesime
FROM ref.source s
LEFT JOIN LATERAL (
  SELECT DISTINCT ON (fichier_nom) fichier_nom, statut, debut
  FROM ingest.import
  WHERE source_id = s.source_id
  ORDER BY fichier_nom, debut DESC
) d ON true
LEFT JOIN LATERAL (
  SELECT fin, millesime
  FROM ingest.import
  WHERE source_id = s.source_id AND fichier_nom = d.fichier_nom AND statut = 'PUBLIE'
  ORDER BY fin DESC
  LIMIT 1
) p ON true;
