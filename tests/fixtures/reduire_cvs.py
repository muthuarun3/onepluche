"""Fabrique l'extrait de test du cube de l'enquête Cadre de vie et sécurité (SSMSI).

Vrai extrait (Licence Ouverte 2.0) : les trois modules du sentiment d'insécurité et un
module de victimation, pour l'ensemble et par taille d'agglomération (lignes à ignorer).

    uv run python tests/fixtures/reduire_cvs.py <cube complet> <cube réduit>
"""

import csv
import sys

MODULES = (
    "Sentiment d’insécurité dans le quartier ou le village",
    "Sentiment d’insécurité au domicile",
    "Renoncement à sortir seul de chez soi pour des raisons de sécurité",
    "Vol ou tentative de vol avec violences ou menaces",
)


def reduire(source: str, cible: str) -> None:
    with open(source, encoding="utf-8-sig", newline="") as entree:
        lecteur = csv.DictReader(entree)
        lignes = [
            x
            for x in lecteur
            if x["MODULE_ENQUETE"] in MODULES
            and x["VENTILATION"] in ("", "Taille de l'agglomération")
        ]
        colonnes = lecteur.fieldnames
    with open(cible, "w", encoding="utf-8", newline="") as sortie:
        ecrivain = csv.DictWriter(sortie, colonnes, quoting=csv.QUOTE_NONNUMERIC)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
