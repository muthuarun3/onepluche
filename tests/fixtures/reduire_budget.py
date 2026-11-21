"""Réduit les réponses Melodi des comptes nationaux (Licence Ouverte 2.0).

    uv run python tests/fixtures/reduire_budget.py <JSON assemblé> <cible.json>

Garde les observations des postes retenus (13 postes et total, ou dépenses pré-engagées),
de 2015 à la dernière année.
"""

import json
import sys

from demographie.imports.connecteurs.besoins import POSTES_CONSO

RETENUS = {*POSTES_CONSO, "CPDPE"}

if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as entree:
        contenu = json.load(entree)
    contenu["observations"] = [
        o
        for o in contenu["observations"]
        if o["dimensions"]["EXPENDITURE"] in RETENUS and o["dimensions"]["TIME_PERIOD"] >= "2015"
    ]
    with open(sys.argv[2], "w", encoding="utf-8") as sortie:
        json.dump(contenu, sortie, sort_keys=True)
