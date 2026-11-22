"""Fabrique les fichiers de test des projections Omphale 2022 (INSEE) à partir des fichiers
complets « donnees_det_<scénario>.xlsx » : mêmes feuilles, en ne gardant que six
départements (dont deux d'outre-mer et un dont le nom diffère du référentiel) et les
colonnes des années lues par le connecteur.

    uv run python tests/fixtures/reduire_omphale.py <fichier INSEE complet> <fichier réduit>
"""

import re
import sys

import openpyxl

from demographie.imports.connecteurs.omphale import ANNEES

DEPARTEMENTS = {"Ain", "Corse-du-Sud", "Creuse", "Paris", "Réunion", "Mayotte"}


def _garder(nom: object) -> bool:
    m = re.fullmatch(r"(?:POP_)?(\d{4})", str(nom))
    return m is None or int(m[1]) in ANNEES


def reduire(source: str, cible: str) -> None:
    entree = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sortie = openpyxl.Workbook()
    sortie.remove(sortie.active)
    for feuille_entree in entree.worksheets:
        feuille = sortie.create_sheet(feuille_entree.title)
        indices = None
        for rang in feuille_entree.iter_rows(values_only=True):
            if not any(v is not None for v in rang):
                continue
            rang = list(rang)
            while rang and rang[-1] is None:
                rang.pop()
            if rang and rang[0] == "ZONE":
                indices = [i for i, n in enumerate(rang) if _garder(n)]
            elif indices and rang and rang[0] and rang[0] not in DEPARTEMENTS:
                continue
            feuille.append([rang[i] for i in indices if i < len(rang)] if indices else rang)
    sortie.save(cible)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
