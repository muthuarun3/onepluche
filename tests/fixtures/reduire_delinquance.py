"""Fabrique l'extrait de test de la base départementale de la délinquance (SSMSI).

Vrai extrait (Licence Ouverte 2.0) : toutes les années et tous les indicateurs, pour la
Creuse, Paris, la Seine-Saint-Denis, la Corse-du-Sud et la Guadeloupe.

    uv run python tests/fixtures/reduire_delinquance.py <CSV complet> <CSV réduit>
"""

import sys

DEPARTEMENTS = {'"23"', '"75"', '"93"', '"2A"', '"971"'}


def reduire(source: str, cible: str) -> None:
    with open(source, encoding="utf-8-sig") as entree, open(cible, "w", encoding="utf-8") as sortie:
        sortie.write("﻿" + next(entree))
        for ligne in entree:
            if ligne.split(";", 1)[0] in DEPARTEMENTS:
                sortie.write(ligne)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
