"""Fabrique le fond de carte des départements : static/carte-departements.js.

    uv run python outils/carte_departements.py <departements-avec-outre-mer.geojson>

Source : contours IGN Admin Express COG (Licence Ouverte), mis en GeoJSON par
github.com/gregoiredavid/france-geojson (fichier « departements-avec-outre-mer »). Les
tracés sont simplifiés (Douglas-Peucker), les coordonnées arrondies, et les cinq
départements d'outre-mer ramenés en médaillons à l'ouest de la métropole, à une taille
lisible (pas à l'échelle). Le résultat (environ 300 Ko) est versionné : la carte ne dépend
d'aucun service extérieur.
"""

import json
import math
import sys
from pathlib import Path

SORTIE = Path(__file__).resolve().parents[1] / "src/demographie/web/static/carte-departements.js"
TOLERANCE = 0.012  # degrés (environ 1 km)
DECIMALES = 3
# Médaillons : (longitude, latitude) du coin bas-gauche et hauteur en degrés de latitude.
MEDAILLONS = {
    "971": (-7.6, 47.6, 0.9),
    "972": (-7.6, 46.4, 0.9),
    "973": (-7.6, 44.4, 1.6),
    "974": (-7.6, 43.2, 0.9),
    "976": (-7.6, 42.1, 0.8),
}


def _distance(p, a, b):
    if a == b:
        return math.dist(p, a)
    (x, y), (x1, y1), (x2, y2) = p, a, b
    return abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / math.dist(a, b)


def simplifier(points: list, tolerance: float) -> list:
    """Douglas-Peucker itératif ; garde le premier et le dernier point."""
    if len(points) < 3:
        return points
    garder = [False] * len(points)
    garder[0] = garder[-1] = True
    pile = [(0, len(points) - 1)]
    while pile:
        debut, fin = pile.pop()
        loin, indice = 0.0, None
        for i in range(debut + 1, fin):
            d = _distance(points[i], points[debut], points[fin])
            if d > loin:
                loin, indice = d, i
        if indice is not None and loin > tolerance:
            garder[indice] = True
            pile += [(debut, indice), (indice, fin)]
    return [p for p, g in zip(points, garder, strict=True) if g]


def _polygones(geometrie: dict) -> list:
    if geometrie["type"] == "Polygon":
        return [geometrie["coordinates"]]
    return geometrie["coordinates"]


def _deplacer(polygones: list, code: str) -> list:
    if code not in MEDAILLONS:
        return polygones
    x0, y0, hauteur = MEDAILLONS[code]
    points = [p for poly in polygones for anneau in poly for p in anneau]
    xmin = min(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    echelle = hauteur / (ymax - ymin)
    # Corrige l'écart de latitude : un degré de longitude est plus long sous les tropiques.
    rapport = math.cos(math.radians((ymin + ymax) / 2)) / math.cos(math.radians(46.5))
    return [
        [
            [[x0 + (x - xmin) * echelle * rapport, y0 + (y - ymin) * echelle] for x, y in anneau]
            for anneau in poly
        ]
        for poly in polygones
    ]


def fabriquer(source: Path) -> dict:
    entree = json.loads(source.read_text(encoding="utf-8"))
    entites = []
    for f in entree["features"]:
        code = f["properties"]["code"]
        polygones = []
        for poly in _deplacer(_polygones(f["geometry"]), code):
            anneaux = []
            for anneau in poly:
                tolerance = TOLERANCE * (0.3 if code in MEDAILLONS else 1)
                reduit = simplifier(anneau, tolerance)
                if len(reduit) >= 4:
                    anneaux.append([[round(x, DECIMALES), round(y, DECIMALES)] for x, y in reduit])
            if anneaux:
                polygones.append(anneaux)
        entites.append(
            {
                "type": "Feature",
                "properties": {"name": code, "nom": f["properties"]["nom"]},
                "geometry": {"type": "MultiPolygon", "coordinates": polygones},
            }
        )
    entites.sort(key=lambda e: e["properties"]["name"])
    return {"type": "FeatureCollection", "features": entites}


if __name__ == "__main__":
    carte = fabriquer(Path(sys.argv[1]))
    entete = (
        "// Départements de France (IGN Admin Express COG, Licence Ouverte), simplifiés ;\n"
        "// outre-mer en médaillons. Généré par outils/carte_departements.py.\n"
    )
    contenu = json.dumps(carte, separators=(",", ":"), ensure_ascii=False)
    SORTIE.write_text(f"{entete}window.CARTE_DEPARTEMENTS = {contenu};\n", encoding="utf-8")
    print(SORTIE, SORTIE.stat().st_size, "octets,", len(carte["features"]), "départements")
