"""Fabrique les extraits de test de l'énergie (Licence Ouverte) :
- Agence ORE : la Creuse et Paris ;
- ADEME : les comptages par département, gardés en entier (50 Ko) ;
- INSEE IPC : les mois depuis janvier 2024.

    uv run python tests/fixtures/reduire_energie.py <dossier des fichiers téléchargés>
"""

import json
import re
import shutil
import sys
from pathlib import Path

ICI = Path(__file__).parent


def reduire(dossier: str) -> None:
    source = Path(dossier)
    for nom in ("ore-residentiel-electricite.json", "ore-residentiel-gaz.json"):
        contenu = json.loads((source / nom).read_text(encoding="utf-8"))
        contenu["lignes"] = [x for x in contenu["lignes"] if x["code_departement"] in ("23", "75")]
        (ICI / nom).write_text(json.dumps(contenu, sort_keys=True, indent=0), encoding="utf-8")
    shutil.copyfile(
        source / "ademe-dpe-logements-existants.json", ICI / "ademe-dpe-logements-existants.json"
    )
    xml = (source / "ipc-base-2025.xml").read_text(encoding="utf-8")
    xml = re.sub(r'<Obs TIME_PERIOD="(19|200|201|202[0-3])[^>]*/>', "", xml)
    (ICI / "ipc-base-2025.xml").write_text(xml, encoding="utf-8")


if __name__ == "__main__":
    reduire(sys.argv[1])
