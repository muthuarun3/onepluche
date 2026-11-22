"""Fabrique les extraits de test des transports et des courses (Licence Ouverte 2.0) :
- prix des carburants : les relevés agrégés, gardés en entier (4 Ko chacun) ;
- recensement (trajets domicile-travail, voitures) : territoires de reduire_recensement ;
- comptes nationaux (carburants) : depuis 2015.

    uv run python tests/fixtures/reduire_transports.py <dossier des fichiers téléchargés>
"""

import json
import shutil
import sys
from pathlib import Path

from reduire_recensement import reduire as reduire_recensement

ICI = Path(__file__).parent


def reduire(dossier: str) -> None:
    source = Path(dossier)
    for carburant in ("gazole", "e10"):
        nom = f"prix-carburants-{carburant}.json"
        shutil.copyfile(source / nom, ICI / nom)
    for nom in ("DS_RP_NAVETTES_PRINC_mode.json", "DS_RP_LOGEMENT_PRINC_voitures.json"):
        reduire_recensement(str(source / nom), str(ICI / nom))
    nom = "DD_CNA_CONSO_MENAGES_COICOP_carburants.json"
    contenu = json.loads((source / nom).read_text(encoding="utf-8"))
    contenu["observations"] = [
        o for o in contenu["observations"] if o["dimensions"]["TIME_PERIOD"] >= "2015"
    ]
    (ICI / nom).write_text(json.dumps(contenu, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    reduire(sys.argv[1])
