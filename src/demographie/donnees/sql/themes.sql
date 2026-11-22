-- Rubriques et leurs thèmes (une ligne par rubrique sans thème, theme NULL).
SELECT rubrique, rubrique_libelle, rubrique_chemin, theme, theme_libelle
FROM api.theme
ORDER BY rubrique_ordre, theme_ordre NULLS FIRST;
