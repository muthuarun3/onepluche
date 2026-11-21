"""Fabrique l'extrait de test du classeur APL de la DREES (Licence Ouverte 2.0).

    uv run python tests/fixtures/reduire_soins.py <classeur APL médecins généralistes> <cible.xlsx>

Feuilles « APL <année> » seules, lignes d'en-tête et communes de la Creuse et de Paris.
Le jeu de l'Assurance maladie (ALD sans médecin traitant) et les quatre jeux BPE sont
versionnés tels que téléchargés : quelques centaines de lignes chacun.
"""

import sys

from openpyxl import Workbook, load_workbook

DEPARTEMENTS = ("23", "75")


def apl(source: str, cible: str) -> None:
    classeur = load_workbook(source, read_only=True)
    sortie = Workbook()
    sortie.remove(sortie.active)
    for nom in classeur.sheetnames:
        if not nom.startswith("APL "):
            continue
        reduite = sortie.create_sheet(nom)
        entete_vue = False
        for rang in classeur[nom].iter_rows(values_only=True):
            if not entete_vue:
                reduite.append(rang)
                entete_vue = rang[0] == "Code commune INSEE"
            elif rang[0] is None or str(rang[0])[:2] in DEPARTEMENTS:
                reduite.append(rang)
    sortie.save(cible)


if __name__ == "__main__":
    apl(sys.argv[1], sys.argv[2])
