"""Fabrique un extrait de test d'un jeu Melodi (CSV zippé) : années 2023 à 2025 seulement.

Extrait réel INSEE (Licence Ouverte 2.0) : mêmes colonnes, mêmes lignes, moins d'années.

    uv run python tests/fixtures/reduire_melodi.py <archive complète> <archive réduite>
"""

import sys
import zipfile

ANNEES = ("2023", "2024", "2025")


def reduire(source: str, cible: str) -> None:
    with (
        zipfile.ZipFile(source) as entree,
        zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as sortie,
    ):
        for nom in entree.namelist():
            lignes = entree.read(nom).decode("utf-8").splitlines(keepends=True)
            if nom.endswith("_data.csv"):
                entete = lignes[0].strip().split(";")
                rang_annee = entete.index('"TIME_PERIOD"')
                lignes = [lignes[0]] + [
                    ligne for ligne in lignes[1:] if ligne.split(";")[rang_annee] in ANNEES
                ]
            sortie.writestr(nom, "".join(lignes))


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
