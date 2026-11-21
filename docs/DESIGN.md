# Design Brief — Charte UI-UX

**État au :** 21 novembre 2026. La source de vérité est
[`src/demographie/web/static/style.css`](../src/demographie/web/static/style.css) : ce
document en explique les règles. La vitrine Neocities (`vitrine/index.html`) reprend la même
direction artistique et les mêmes couleurs.

## 1. Intention

**Sobre, lisible, digne de confiance.** On épluche ressemble à une publication statistique
claire, pas à un tableau de bord marketing. Le chiffre et sa phrase passent avant la
décoration. Chaque chiffre a sa source juste en dessous, en plus petit et plus pâle.

- Une idée par bloc : un titre, une phrase avec le chiffre en gras, quelques chiffres ou
  barres, la source.
- Pas d'animations, pas d'illustrations, pas d'icônes décoratives, pas de dégradés.
- Pas de « score », de couleur rouge/vert qui jugerait un département.

## 2. Couleurs (jetons CSS)

Toutes les couleurs passent par des variables définies sur `:root`. Aucune couleur écrite en
dur dans un gabarit ou dans `app.js` (le JavaScript lit les variables avec
`getComputedStyle`).

| Jeton | Clair | Sombre | Usage |
| --- | --- | --- | --- |
| `--fond` | `#f6f6f4` | `#121211` | Fond de page |
| `--surface` | `#fcfcfb` | `#1a1a19` | Blocs, cartes, barre latérale |
| `--texte` | `#0b0b0b` | `#f0efec` | Texte principal, chiffres |
| `--texte-2` | `#52514e` | `#c3c2b7` | Phrases secondaires, libellés |
| `--texte-3` | `#7a7974` | `#94938b` | Notes, codes, pied de page |
| `--bordure` | `#e2e1dc` | `#33332f` | Contours des blocs |
| `--grille` | `#ecebe7` | `#2a2a27` | Lignes de tableau, grilles de graphiques, survol de menu |
| `--lien` | `#1c5cab` | `#86b6ef` | Liens, titres de questions |
| `--serie` | `#2a78d6` | `#3987e5` | Couleur de donnée par défaut : barres, courbes, accent du bandeau, entrée active du menu |
| `--hommes` | `#2a78d6` | `#3987e5` | Pyramide : hommes |
| `--femmes` | `#eb6834` | `#d95926` | Pyramide : femmes |

Règles :

- **Une seule couleur de série** pour une donnée simple (`--serie`). Une deuxième couleur
  seulement quand la donnée a deux catégories (hommes / femmes). Pour comparer à la France :
  même couleur, la France en trait ou en barre plus pâle (`--texte-3`), jamais une couleur
  « bonne » ou « mauvaise ».
- Années provisoires : même couleur, **trait pointillé**.
- Contraste texte / fond au moins 4,5:1 (AA) dans les deux thèmes.
- `@media (forced-colors: active)` : les barres passent en `CanvasText`.
- Un nouveau jeton se déclare dans les trois blocs (clair, sombre automatique, sombre forcé)
  et se reporte dans la vitrine.

## 3. Mode sombre et mode clair

- Par défaut, l'appli suit le réglage du système (`prefers-color-scheme`).
- L'attribut `data-theme="light"` ou `data-theme="dark"` sur `<html>` force un thème ; il
  n'y a pas encore de bouton pour le choisir (hors périmètre tant que Muthu ne le demande
  pas).
- `color-scheme` est déclaré pour que les contrôles natifs (listes, barres de défilement)
  suivent le thème.

## 4. Typographie

| Élément | Règle |
| --- | --- |
| Police | Police du système : `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Aucune police téléchargée. |
| Corps | 16 px, interligne 1,5 |
| `h1` | 1,75rem (1,4rem sur téléphone) |
| `h2` | 1,15rem ; titre d'une question sur l'accueil : 1,2rem, gras, couleur `--lien` |
| Chiffre clé | 1,5rem, gras (1,2rem dans un bloc sur téléphone) |
| Libellés, sources, notes | 0,75 à 0,9rem, couleurs `--texte-2` ou `--texte-3` |
| Chiffres | `font-variant-numeric: tabular-nums` partout où des nombres s'alignent |

Format des nombres (filtres Jinja `entier`, `millions`, `pct`) : à la française.

- Séparateur de milliers : espace fine insécable (`69 081 996`).
- Décimale : virgule (`28,5`).
- Pourcentage : espace insécable avant `%` (`28,5 %`).
- Grands effectifs : « 69,1 millions ».

## 5. Mise en page

| Élément | Ordinateur | Téléphone (moins de 48rem / 40rem) |
| --- | --- | --- |
| Cadre (🔶 PR #21) | Grille : barre latérale 15rem fixe + colonne de contenu | Une colonne ; la barre latérale devient une barre du haut, liens en ligne |
| Contenu | Largeur max 64rem, marges 1rem | Pleine largeur, marges 1rem |
| Blocs du résumé | Grille auto, colonnes d'au moins 28rem | Une colonne |
| Chiffres clés | Grille auto, colonnes d'au moins 10rem | Idem, passent à la ligne |
| Graphiques | Hauteur 26rem | Hauteur 22rem |
| Tableaux larges | — | Défilent seuls (`.tableau-defilant`), jamais la page |

**Règle absolue : aucun défilement horizontal de la page à 390 px de large.** Chaque
changement d'interface est vérifié à 1280 px et 390 px.

## 6. Composants

| Composant | Classe | Règle |
| --- | --- | --- |
| Bandeau | `.bandeau` | Surface, bordure, **filet gauche de 4px `--serie`**, texte 1,05rem. Un seul par page (accueil). |
| Carte de question | `.question` | Surface, bordure, rayon 8px ; titre en `--lien`, résumé en `--texte-2` ; survol : bordure `--serie`. Toute la carte est cliquable. |
| Bloc | `.bloc` | Surface, bordure, rayon 8px, marge interne 1rem 1,25rem. Ordre : `h2`, `.phrase`, chiffres ou barres, `.source`, lien `.detail`. |
| Chiffre clé | `.chiffre` | Libellé au-dessus (petit, `--texte-2`), valeur dessous (grande, gras), note facultative (`--texte-3`). Définition en infobulle (`title`). |
| Barres horizontales | `.barres` | En HTML/CSS pur (pas d'ECharts) : libellé, piste, barre `--serie` arrondie à droite, valeur en % alignée à droite. Largeur relative à la plus grande barre. |
| Graphique | `.graphique-bloc` | Bloc avec titre et contrôle (liste) sur la même ligne, légende sous le titre, tableau équivalent dans un `<details>` « Voir le tableau ». |
| Source | `.source` | 0,85rem, `--texte-2` : producteur (lien), licence, date de mise à jour, avertissement. |
| Menu latéral | `.barre-laterale` | Liens `--texte-2` ; survol fond `--grille` ; page courante : fond `--grille`, gras, filet gauche intérieur 3px `--serie`. |
| État d'import | `.etat-*` | Préfixe texte « ✓ » ou « ! » : l'état ne repose jamais sur la couleur seule. |
| Fil d'Ariane | `.fil` | Texte `--texte-2`, séparateur « › ». |
| Onglets | `.onglets` | Liens en pilule, bordure `--bordure` ; page courante : fond `--serie`, texte `--surface`. |
| Carte des départements | `.graphique.carte` | Une seule teinte de `--grille` (valeur basse) à `--serie` (valeur haute), jamais de couleur « bonne » ou « mauvaise » ; sans donnée : fond `--fond` et liste sous le classement ; le classement sert de tableau équivalent. |

Rayon des coins : 8px (blocs), 6px (liens du menu), 2px (pastilles de légende).
Bordures : 1px `--bordure`. Pas d'ombres dans l'appli.

## 7. Graphiques (ECharts)

- Fichier local `static/echarts.min.js`, chargé seulement sur les pages qui en ont besoin.
- Couleurs, textes, grilles et infobulles lus depuis les jetons CSS ; un changement de thème
  du système redessine les graphiques.
- Données passées au navigateur dans `<script type="application/json" id="donnees">`, jamais
  par un appel d'API en JavaScript.
- Chaque graphique a `role="img"`, un `aria-label` et un tableau équivalent.
- Infobulles : fond `--surface`, bordure `--bordure`, texte 13px, nombres au format
  français (`Intl.NumberFormat("fr-FR")`).
- Carte des départements (prévue) : une teinte séquentielle unique dérivée de `--serie`,
  légende des classes, valeur France indiquée ; départements sans donnée en hachures ou gris
  `--grille`, avec la mention « pas de donnée ».

## 8. Rédaction

- Français, phrases complètes, vouvoiement implicite (pas de « tu »).
- Les phrases sont des modèles fixes remplis par les données : jamais d'adjectif qui juge
  (« inquiétant », « bon »). On compare : « plus que », « contre Y en France ».
- Un calcul d'On épluche est annoncé comme tel (« calcul On épluche »), avec sa formule.
- Les définitions distinctes gardent des libellés distincts : « chômage au sens du BIT »
  contre « chômeurs déclarés » ; « retraités (pensionnés) » contre « retraités déclarés ».

## 9. Accessibilité

- HTML sémantique (`header`, `nav`, `main`, `section`, `figure`), langue `fr`.
- Liens et contrôles atteignables au clavier ; focus visible (`:focus-visible`).
- Contenus repliables en `<details>` natifs ; aucune interaction réservée à la souris.
- Pages utilisables sans JavaScript, sauf le dessin des graphiques (tableaux disponibles).

## 10. Performance

- Moins de 300 Ko transférés par page hors ECharts (mis en cache).
- Une seule feuille de style, un seul script applicatif, aucune ressource externe (CSP
  `default-src 'self'`).
