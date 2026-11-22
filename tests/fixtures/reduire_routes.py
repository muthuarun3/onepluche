"""Fabrique les archives de test des accidents de la route (ONISR, fichiers BAAC).

Vrais extraits (Licence Ouverte 2.0) : on ne garde que les accidents de quelques
départements (Creuse, Corse-du-Sud, Guadeloupe) et des collectivités de Saint-Barthélemy
et de Saint-Martin, dans le format d'origine de chaque année (avant 2019 : virgules,
Latin-1, département sur trois chiffres ; depuis : points-virgules, UTF-8).

    uv run python tests/fixtures/reduire_routes.py <caractéristiques> <usagers> <archive.zip>
"""

import csv
import io
import sys
import zipfile
from pathlib import Path

GARDES = {"23", "2A", "971", "977", "978", "230", "201"}


def _lire(chemin: str) -> tuple[list[dict], list[str], str, str]:
    brut = Path(chemin).read_bytes()
    try:
        texte, encodage = brut.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        texte, encodage = brut.decode("latin-1"), "latin-1"
    premiere = texte.split("\n", 1)[0]
    separateur = ";" if premiere.count(";") > premiere.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(texte, newline=""), delimiter=separateur)
    return list(lecteur), lecteur.fieldnames, separateur, encodage


def _ecrire(lignes, colonnes, separateur, encodage) -> bytes:
    sortie = io.StringIO(newline="")
    quoting = csv.QUOTE_ALL if separateur == ";" else csv.QUOTE_MINIMAL
    ecrivain = csv.DictWriter(sortie, colonnes, delimiter=separateur, quoting=quoting)
    ecrivain.writeheader()
    ecrivain.writerows(lignes)
    return sortie.getvalue().encode(encodage)


def reduire(caracteristiques: str, usagers: str, cible: str) -> None:
    lieux, colonnes, sep, enc = _lire(caracteristiques)
    gardes = [x for x in lieux if x["dep"].strip() in GARDES]
    accidents = {x["Num_Acc"] for x in gardes}
    personnes, colonnes_u, sep_u, enc_u = _lire(usagers)
    gardes_u = [x for x in personnes if x["Num_Acc"] in accidents]
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in (
            ("caracteristiques.csv", _ecrire(gardes, colonnes, sep, enc)),
            ("usagers.csv", _ecrire(gardes_u, colonnes_u, sep_u, enc_u)),
        ):
            archive.writestr(zipfile.ZipInfo(nom, (2000, 1, 1, 0, 0, 0)), contenu)


if __name__ == "__main__":
    reduire(*sys.argv[1:4])
