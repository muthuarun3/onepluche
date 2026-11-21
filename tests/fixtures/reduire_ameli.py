"""Fabrique un extrait de test de l'export Ameli : années 2023 et 2024 seulement.

Extrait réel (Licence Ouverte 2.0), tous départements, pour que leur somme reste proche
du total national publié.

    uv run python tests/fixtures/reduire_ameli.py <export complet> <export réduit>
"""

import csv
import sys


def reduire(source: str, cible: str) -> None:
    with (
        open(source, encoding="utf-8-sig", newline="") as f,
        open(cible, "w", encoding="utf-8", newline="") as g,
    ):
        lecteur = csv.DictReader(f, delimiter=";")
        ecrivain = csv.DictWriter(g, ["annee", "top", "region", "dept", "ntop"], delimiter=";")
        ecrivain.writeheader()
        lignes = [r for r in lecteur if r["annee"] >= "2023"]
        lignes.sort(key=lambda r: (r["annee"], r["region"], r["dept"], r["top"]))
        ecrivain.writerows({k: r[k] for k in ecrivain.fieldnames} for r in lignes)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
