"""Carte de France pour choisir un territoire, dessinée en SVG côté serveur.

Les tracés (``contours.json``) sont préparés une fois par ``outils/contours_svg.py`` à
partir d'IGN Admin Express (Licence ouverte). La carte montre la métropole seulement ; les
territoires sans tracé (outre-mer) sont proposés à côté, en boutons.
"""

import json
from functools import cache
from pathlib import Path

LIBELLES_NIVEAUX = {"REG": "Régions", "DEP": "Départements"}


@cache
def contours() -> dict:
    return json.loads((Path(__file__).parent / "contours.json").read_text(encoding="utf-8"))


def choix_territoire(tous: list[dict], niveaux: tuple[str, ...], lien: str) -> dict:
    """Ce qu'il faut au gabarit ``_carte.html`` : une vue par niveau (carte + outre-mer).

    ``lien`` contient ``{niveau}`` et ``{code}``, par exemple ``/territoire/{niveau}/{code}``.
    """
    traces = contours()
    vues = []
    for niveau in niveaux:
        liste = [t for t in tous if t["niveau"] == niveau]

        def adresse(code: str, niveau: str = niveau) -> str:
            return lien.format(niveau=niveau, code=code)

        sur_carte = [
            {
                "code": t["code"],
                "libelle": t["libelle"],
                "lien": adresse(t["code"]),
                "d": traces[niveau][t["code"]]["d"],
            }
            for t in liste
            if t["code"] in traces[niveau]
        ]
        encart = []
        if niveau == "DEP":
            encart = [
                {
                    "code": t["code"],
                    "libelle": t["libelle"],
                    "lien": adresse(t["code"]),
                    "d": traces["encart"]["territoires"][t["code"]]["d"],
                }
                for t in liste
                if t["code"] in traces["encart"]["territoires"]
            ]
        vues.append(
            {
                "niveau": niveau,
                "libelle": LIBELLES_NIVEAUX[niveau],
                "sur_carte": sur_carte,
                "encart": encart,
                "outre_mer": [
                    {"code": t["code"], "libelle": t["libelle"], "lien": adresse(t["code"])}
                    for t in liste
                    if t["code"] not in traces[niveau]
                ],
            }
        )
    return {
        "viewBox": traces["viewBox"],
        "cadre_encart": traces["encart"]["cadre"],
        "vues": vues,
    }
