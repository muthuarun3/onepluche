"""Fabrique l'extrait de test de DVF : les ventes de la Creuse d'une année (Licence Ouverte).

uv run python tests/fixtures/reduire_dvf.py <full.csv.gz> tests/fixtures/dvf-2025.csv.gz
"""

import gzip
import sys


def reduire(source: str, cible: str) -> None:
    with gzip.open(source, "rt", encoding="utf-8") as entree:
        entete = entree.readline()
        colonne = entete.split(",").index("code_departement")
        lignes = [entete] + [x for x in entree if x.split(",")[colonne] == "23"]
    with gzip.open(cible, "wt", encoding="utf-8", compresslevel=9) as sortie:
        sortie.writelines(lignes)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
