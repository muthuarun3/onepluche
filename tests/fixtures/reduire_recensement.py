"""Fabrique un extrait de test d'un jeu du recensement téléchargé par l'API Melodi.

Garde la France, l'Île-de-France, la Creuse, Paris, la Guadeloupe et La Réunion
(Licence Ouverte 2.0).

    uv run python tests/fixtures/reduire_recensement.py <fichier complet> <fichier réduit>
"""

import json
import sys

GEO = {"2026-FRANCE-F", "2026-FRANCE-FM", "2026-REG-11", "2026-DEP-23", "2026-DEP-75",
       "2026-DEP-971", "2026-DEP-974"}  # fmt: skip
# Modalités jamais lues par les connecteurs : inutile de les garder.
IGNORES = {("STUD", "0"), ("AGE", "Y_GE2")}


def reduire(source: str, cible: str) -> None:
    with open(source, encoding="utf-8") as f:
        contenu = json.load(f)
    contenu["observations"] = [
        o
        for o in contenu["observations"]
        if o["dimensions"]["GEO"] in GEO and not set(o["dimensions"].items()) & IGNORES
    ]
    with open(cible, "w", encoding="utf-8") as f:
        json.dump(contenu, f, sort_keys=True, indent=0)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
