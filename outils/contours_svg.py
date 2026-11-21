"""Prépare les contours de la carte de choix du territoire (France métropolitaine).

Entrée : les GeoJSON simplifiés de france-geojson, tirés d'IGN Admin Express COG (Licence
ouverte) : https://github.com/gregoiredavid/france-geojson, fichiers
``departements-version-simplifiee.geojson`` et ``regions-version-simplifiee.geojson``.

Sortie : ``src/demographie/web/contours.json``, des tracés SVG déjà projetés (un par
territoire), que les gabarits dessinent sans JavaScript ni bibliothèque.

Usage :
    python outils/contours_svg.py departements.geojson regions.geojson

Projection équirectangulaire centrée sur 46,5° N (écart négligeable à cette échelle),
1 unité = environ 1,1 km ; tracés simplifiés (Douglas-Peucker, 1,5 unité), invisible à la
taille d'affichage (la carte fait la largeur d'un téléphone).
"""

import json
import math
import sys
from pathlib import Path

LON_MIN, LAT_MAX = -5.3, 51.15
ECHELLE = 100.0  # unités par degré de latitude
COS = math.cos(math.radians(46.5))
TOLERANCE = 1.5
LARGEUR, HAUTEUR = 1030, 1000
# Encart « Paris et petite couronne », en bas à gauche (l'Atlantique y est vide).
ENCART_CODES = ("75", "92", "93", "94")
ENCART_CADRE = (0, 690, 240, 300)  # x, y, largeur, hauteur dans la carte
ENCART_LEGENDE = 70  # bas du cadre réservé au titre de l'encart
SORTIE = Path(__file__).resolve().parent.parent / "src/demographie/web/contours.json"


def _projeter(lon, lat):
    return ((lon - LON_MIN) * COS * ECHELLE, (LAT_MAX - lat) * ECHELLE)


def _distance(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - x1 - t * dx, y - y1 - t * dy)


def _douglas_peucker(points, tolerance):
    garder = [False] * len(points)
    garder[0] = garder[-1] = True
    piles = [(0, len(points) - 1)]
    while piles:
        debut, fin = piles.pop()
        loin, indice = 0.0, None
        for i in range(debut + 1, fin):
            d = _distance(points[i], points[debut], points[fin])
            if d > loin:
                loin, indice = d, i
        if indice is not None and loin > tolerance:
            garder[indice] = True
            piles += [(debut, indice), (indice, fin)]
    return [p for p, g in zip(points, garder, strict=True) if g]


def _anneau(points, tolerance, decimales):
    """Anneau projeté et simplifié ; None s'il devient trop petit pour être vu."""
    ouvert = points[:-1] if points[0] == points[-1] else points
    if len(ouvert) < 3:
        return None
    milieu = len(ouvert) // 2
    a = _douglas_peucker(ouvert[: milieu + 1], tolerance)
    b = _douglas_peucker(ouvert[milieu:] + [ouvert[0]], tolerance)
    resultat = []
    for x, y in a + b[1:-1]:
        p = (round(x, decimales), round(y, decimales))
        if not resultat or p != resultat[-1]:
            resultat.append(p)
    return resultat if len(resultat) >= 3 else None


def _nombre(v):
    texte = f"{v:g}"
    return texte.replace("0.", ".") if texte.startswith(("0.", "-0.")) else texte


def _trace(anneaux):
    """Chemin SVG en coordonnées relatives (« m dx dy l dx dy … z »)."""
    morceaux, precedent = [], (0, 0)
    for anneau in anneaux:
        x0, y0 = anneau[0]
        morceaux.append(
            f"{'M' if not morceaux else 'm'}{_nombre(x0 - precedent[0])} "
            f"{_nombre(y0 - precedent[1])}"
        )
        pas = []
        for (xa, ya), (xb, yb) in zip(anneau, anneau[1:], strict=False):
            pas.append(f"{_nombre(round(xb - xa, 3))} {_nombre(round(yb - ya, 3))}")
        morceaux.append("l" + " ".join(pas) + "z")
        precedent = (x0, y0)
    return "".join(morceaux).replace(" -", "-")


def _polygones(geometrie):
    return (
        [geometrie["coordinates"]] if geometrie["type"] == "Polygon" else geometrie["coordinates"]
    )


def _territoires(chemin, transformer, tolerance, decimales, codes=None):
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    resultat = {}
    for f in sorted(donnees["features"], key=lambda f: f["properties"]["code"]):
        code = f["properties"]["code"]
        if codes is not None and code not in codes:
            continue
        anneaux = []
        for poly in _polygones(f["geometry"]):
            for anneau in poly:
                a = _anneau([transformer(*p) for p in anneau], tolerance, decimales)
                if a is not None:
                    anneaux.append(a)
        resultat[code] = {"nom": f["properties"]["nom"], "d": _trace(anneaux)}
    return resultat


def _encart(chemin):
    """Paris et petite couronne, agrandis pour rester touchables sur un téléphone."""
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    points = [
        _projeter(*p)
        for f in donnees["features"]
        if f["properties"]["code"] in ENCART_CODES
        for poly in _polygones(f["geometry"])
        for anneau in poly
        for p in anneau
    ]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy, larg, haut = ENCART_CADRE
    haut -= ENCART_LEGENDE
    marge = 12
    facteur = min(
        (larg - 2 * marge) / (max(xs) - min(xs)), (haut - 2 * marge) / (max(ys) - min(ys))
    )
    dx = cx + (larg - facteur * (max(xs) - min(xs))) / 2
    dy = cy + (haut - facteur * (max(ys) - min(ys))) / 2

    def transformer(lon, lat):
        x, y = _projeter(lon, lat)
        return (dx + (x - min(xs)) * facteur, dy + (y - min(ys)) * facteur)

    return {
        "cadre": list(ENCART_CADRE),
        "territoires": _territoires(chemin, transformer, 0.8, 1, set(ENCART_CODES)),
    }


def main(departements, regions):
    contenu = {
        "source": "IGN Admin Express COG 2018 via france-geojson, Licence ouverte",
        "viewBox": f"0 0 {LARGEUR} {HAUTEUR}",
        "DEP": _territoires(departements, _projeter, TOLERANCE, 0),
        "REG": _territoires(regions, _projeter, TOLERANCE, 0),
        "encart": _encart(departements),
    }
    SORTIE.write_text(
        json.dumps(contenu, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(SORTIE, SORTIE.stat().st_size, "octets")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
