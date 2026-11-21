"""Fabrique les extraits de test de la Carte des loyers et des poids communaux.

Garde les communes de la Creuse, de Paris (arrondissements) et de la Guadeloupe, et
seulement le millésime 2023 des poids (Licence Ouverte 2.0).

    uv run python tests/fixtures/reduire_loyers.py <dossier des 4 CSV> <poids complet .json>
"""

import json
import sys
from pathlib import Path

ICI = Path(__file__).parent


def _gardee(commune: str) -> bool:
    return commune[:2] in ("23", "75") or commune[:3] == "971"


def reduire(dossier: str, poids: str) -> None:
    for csv in sorted(Path(dossier).glob("carte-loyers-*.csv")):
        lignes = csv.read_bytes().split(b"\r\n")
        gardees = [lignes[0]] + [
            ligne
            for ligne in lignes[1:]
            if ligne and _gardee(ligne.split(b";")[1].strip(b'"').decode())
        ]
        (ICI / csv.name).write_bytes(b"\r\n".join(gardees) + b"\r\n")
    contenu = json.loads(Path(poids).read_text(encoding="utf-8"))
    contenu["observations"] = [
        o
        for o in contenu["observations"]
        if o["dimensions"]["TIME_PERIOD"] == "2023"
        and _gardee(o["dimensions"]["GEO"].split("-", 2)[2])
    ]
    with open(ICI / Path(poids).name, "w", encoding="utf-8") as f:
        json.dump(contenu, f, sort_keys=True, indent=0)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
