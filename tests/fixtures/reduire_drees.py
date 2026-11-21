"""Fabrique les extraits de test des jeux DREES (Licence Ouverte 2.0).

    uv run python tests/fixtures/reduire_drees.py eacr <classeur EACR part 1> <cible.xlsx>
    uv run python tests/fixtures/reduire_drees.py panorama <export CSV> <cible.csv>

EACR : feuille « A-Cadrage » seule, lignes « Tous régimes » et CNAV (bruit à ignorer),
années 2019 à 2024. Panorama : années 2022 à 2024, tous territoires.
"""

import csv
import sys

from openpyxl import Workbook, load_workbook


def eacr(source: str, cible: str) -> None:
    feuille = load_workbook(source, read_only=True)["A-Cadrage"]
    feuille.reset_dimensions()
    sortie = Workbook()
    reduite = sortie.active
    reduite.title = "A-Cadrage"
    for i, rang in enumerate(feuille.iter_rows(values_only=True)):
        if i == 0 or (rang[0] >= 2019 and rang[2] in ("0000", "0010")):
            reduite.append(rang)
    sortie.save(cible)


def panorama(source: str, cible: str) -> None:
    with (
        open(source, encoding="utf-8-sig", newline="") as f,
        open(cible, "w", encoding="utf-8", newline="") as g,
    ):
        lecteur = csv.DictReader(f, delimiter=";")
        ecrivain = csv.DictWriter(g, lecteur.fieldnames, delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(r for r in lecteur if r["annee"] in ("2022", "2023", "2024"))


if __name__ == "__main__":
    {"eacr": eacr, "panorama": panorama}[sys.argv[1]](sys.argv[2], sys.argv[3])
