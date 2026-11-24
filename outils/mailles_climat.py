"""Prépare la table des mailles climatiques de chaque département (métropole).

Les projections climatiques de la Banque mondiale (CMIP6, grille de 0,25°) donnent une valeur
par maille d'environ 25 km. Pour en tirer une valeur par département, on calcule une fois la
part de chaque département qui tombe dans chaque maille : 100 points de sondage par maille,
chacun rattaché au département qui le contient.

Entrée : ``departements.geojson`` de france-geojson (IGN Admin Express COG, Licence ouverte) :
https://github.com/gregoiredavid/france-geojson.

Sortie : ``src/demographie/imports/connecteurs/mailles_climat.csv`` : département, latitude et
longitude du centre de la maille, surface du département dans la maille (km², approchée).

Usage :
    python outils/mailles_climat.py departements.geojson
"""

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

PAS = 0.25
SONDAGES = 10  # par côté de maille : 100 points
SORTIE = (
    Path(__file__).resolve().parent.parent
    / "src/demographie/imports/connecteurs/mailles_climat.csv"
)


def _anneaux(geometrie: dict) -> list[list[list[tuple[float, float]]]]:
    """Polygones (anneau extérieur puis trous) d'une géométrie GeoJSON."""
    if geometrie["type"] == "Polygon":
        polygones = [geometrie["coordinates"]]
    else:
        polygones = geometrie["coordinates"]
    return [[[(x, y) for x, y in anneau] for anneau in p] for p in polygones]


def _dans_anneau(x: float, y: float, anneau: list[tuple[float, float]]) -> bool:
    dedans = False
    j = len(anneau) - 1
    for i in range(len(anneau)):
        xi, yi = anneau[i]
        xj, yj = anneau[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dedans = not dedans
        j = i
    return dedans


def _dans(x: float, y: float, polygones) -> bool:
    for anneaux in polygones:
        if _dans_anneau(x, y, anneaux[0]) and not any(
            _dans_anneau(x, y, trou) for trou in anneaux[1:]
        ):
            return True
    return False


def _boite(polygones):
    xs = [x for p in polygones for x, _ in p[0]]
    ys = [y for p in polygones for _, y in p[0]]
    return min(xs), min(ys), max(xs), max(ys)


def _km2_sondage(lat: float) -> float:
    cote = PAS * 111.32 / SONDAGES
    return cote * cote * math.cos(math.radians(lat))


def mailles(geojson: dict) -> list[tuple[str, float, float, float]]:
    resultat = []
    for entite in geojson["features"]:
        code = entite["properties"]["code"]
        polygones = _anneaux(entite["geometry"])
        x0, y0, x1, y1 = _boite(polygones)
        comptes: dict[tuple[float, float], int] = defaultdict(int)
        # Centres de mailles : multiples de 0,25° (grille de la Banque mondiale).
        lat = round(y0 / PAS) * PAS
        while lat - PAS / 2 <= y1:
            lon = round(x0 / PAS) * PAS
            while lon - PAS / 2 <= x1:
                for i in range(SONDAGES):
                    for j in range(SONDAGES):
                        y = lat - PAS / 2 + (i + 0.5) * PAS / SONDAGES
                        x = lon - PAS / 2 + (j + 0.5) * PAS / SONDAGES
                        if x0 <= x <= x1 and y0 <= y <= y1 and _dans(x, y, polygones):
                            comptes[(lat, lon)] += 1
                lon += PAS
            lat += PAS
        if not comptes:
            raise SystemExit(f"Aucune maille pour le département {code}")
        for (lat, lon), n in sorted(comptes.items()):
            resultat.append((code, round(lat, 2), round(lon, 2), round(n * _km2_sondage(lat), 1)))
    return resultat


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    geojson = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    lignes = mailles(geojson)
    with SORTIE.open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["departement", "latitude", "longitude", "km2"])
        ecrivain.writerows(lignes)
    print(f"{len({ligne[0] for ligne in lignes})} départements, {len(lignes)} lignes -> {SORTIE}")


if __name__ == "__main__":
    main()
