"""Fabrique les fichiers de test à partir des fichiers INSEE complets.

Les fichiers produits sont de vrais extraits INSEE (Licence Ouverte 2.0) : mêmes
feuilles, mêmes cellules, en ne gardant que quelques années représentatives :
2024-2026 (provisoires), 1995 (second tableau outre-mer, tranche « 90 ans et plus »)
et 1975 (France métropolitaine seule).

    uv run python tests/fixtures/reduire.py <fichier INSEE complet> <fichier réduit>
"""

import sys

import openpyxl

ANNEES = ("2026", "2025", "2024", "1995", "1975")


def reduire(source: str, cible: str) -> None:
    entree = openpyxl.load_workbook(source, read_only=True, data_only=True)
    sortie = openpyxl.Workbook()
    sortie.remove(sortie.active)
    for nom in ANNEES:
        feuille = sortie.create_sheet(nom)
        for rang in entree[nom].iter_rows(values_only=True):
            feuille.append(list(rang))
    sortie.save(cible)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
