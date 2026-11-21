"""Fabrique un extrait de test d'un export ESR : rentrées 2023 et suivantes seulement.

Extrait réel (Licence Ouverte 2.0), tous départements, pour que les totaux recalculés
correspondent aux chiffres publiés.

    uv run python tests/fixtures/reduire_esr.py <export complet> <export réduit>
"""

import csv
import sys


def reduire(source: str, cible: str) -> None:
    with (
        open(source, encoding="utf-8-sig", newline="") as f,
        open(cible, "w", encoding="utf-8", newline="") as g,
    ):
        lecteur = csv.DictReader(f, delimiter=";")
        ecrivain = csv.DictWriter(g, lecteur.fieldnames, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(r for r in lecteur if r["rentree"] >= "2023")


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
