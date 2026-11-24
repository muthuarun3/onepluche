"""Fabrique les extraits de test des demandeurs d'emploi (DARES), de l'enquête BMO et des
contrats et temps partiel (recensement, Melodi).

Extraits réels (Licence Ouverte 2.0) : Gironde, Paris, Guadeloupe et Mayotte, leurs
régions et la France ; demandeurs d'emploi depuis 2024 seulement.

    uv run python tests/fixtures/reduire_dares_bmo.py dares <csv complet> <csv réduit>
    uv run python tests/fixtures/reduire_dares_bmo.py bmo <xlsx complet> <xlsx réduit>
    uv run python tests/fixtures/reduire_dares_bmo.py contrats <json complet> <json réduit>
"""

import csv
import json
import sys

from openpyxl import Workbook, load_workbook

DEPARTEMENTS = {"33", "75", "971", "976"}
REGIONS = {"75", "11", "01", "06"}


def dares(source: str, cible: str) -> None:
    with open(source, encoding="utf-8-sig", newline="") as entree:
        lecteur = csv.DictReader(entree, delimiter=";")
        with open(cible, "w", encoding="utf-8", newline="") as sortie:
            ecrivain = csv.DictWriter(sortie, lecteur.fieldnames, delimiter=";")
            ecrivain.writeheader()
            for ligne in lecteur:
                territoire = ligne["code_departement"] in DEPARTEMENTS or (
                    ligne["code_departement"] == "Total"
                    and (
                        ligne["code_region"] in REGIONS or ligne["code_region"].startswith("Total")
                    )
                )
                if territoire and ligne["date"] >= "2024":
                    ecrivain.writerow(ligne)


def bmo(source: str, cible: str) -> None:
    entree = load_workbook(source, read_only=True)
    sortie = Workbook()
    sortie.active.title = "Description_des_variables"
    for nom in entree.sheetnames:
        if not nom.endswith("_open_data"):
            continue
        feuille = sortie.create_sheet(nom)
        lignes = entree[nom].iter_rows(values_only=True)
        entete = next(lignes)
        feuille.append(entete)
        dept = entete.index("Dept")
        for valeurs in lignes:
            if str(valeurs[dept]) in DEPARTEMENTS:
                feuille.append(valeurs)
    sortie.save(cible)


def contrats(source: str, cible: str) -> None:
    with open(source, encoding="utf-8") as entree:
        contenu = json.load(entree)
    garder = {f"DEP-{d}" for d in DEPARTEMENTS} | {f"REG-{r}" for r in REGIONS}
    garder |= {"FRANCE-F", "FRANCE-FM"}
    contenu["observations"] = [
        o for o in contenu["observations"] if o["dimensions"]["GEO"].split("-", 1)[1] in garder
    ]
    with open(cible, "w", encoding="utf-8") as sortie:
        json.dump(contenu, sortie, sort_keys=True)


if __name__ == "__main__":
    {"dares": dares, "bmo": bmo, "contrats": contrats}[sys.argv[1]](sys.argv[2], sys.argv[3])
