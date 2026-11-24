"""Fabrique l'archive de test de la base GASPAR (Géorisques) à partir de l'archive complète
gaspar.zip : mêmes fichiers catnat et pprn (même nom, mêmes colonnes, mêmes octets par
ligne), en ne gardant que quelques départements, dont un d'outre-mer.

    uv run python tests/fixtures/reduire_gaspar.py <gaspar.zip complet> <archive réduite>
"""

import re
import sys
import zipfile

DEPARTEMENTS = ("23", "13", "974")
_GARDES = re.compile(r"^(catnat|pprn)_gaspar_.*\.csv$")


def _departement(commune: str) -> str:
    return commune[:3] if commune.startswith("97") else commune[:2]


def reduire(source: str, cible: str) -> None:
    with (
        zipfile.ZipFile(source) as entree,
        zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as sortie,
    ):
        for nom in entree.namelist():
            if not _GARDES.match(nom):
                continue
            lignes = entree.read(nom).splitlines(keepends=True)
            entete = lignes[0].decode("utf-8", errors="replace").rstrip("\r\n").split(";")
            colonne = entete.index(
                "code_commune" if nom.startswith("catnat") else "CODE INSEE COMMUNE"
            )
            gardees = [lignes[0]]
            for ligne in lignes[1:]:
                champs = ligne.decode("utf-8", errors="replace").split(";")
                if _departement(champs[colonne].strip()) in DEPARTEMENTS:
                    gardees.append(ligne)
            sortie.writestr(nom, b"".join(gardees))


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
