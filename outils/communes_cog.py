"""Prépare la liste des communes du code officiel géographique (COG) de l'INSEE.

Les indicateurs de risques (appli « Quel avenir ? ») rapportent un nombre de communes à
celui du département. La base GASPAR de Géorisques utilise les codes des communes
actuelles ; la liste du COG sert de dénominateur et écarte les rares codes de communes
disparues (fusions). Elle change peu d'une année à l'autre : on la régénère quand l'INSEE
publie un nouveau COG (janvier).

Entrée : ``v_commune_AAAA.csv`` du COG (https://www.insee.fr/fr/information/2560452).

Sortie : ``src/demographie/imports/connecteurs/communes_cog.csv`` : une colonne
``commune``, les communes de type COM (sans arrondissements municipaux ni communes
déléguées).

Usage :
    python outils/communes_cog.py v_commune_2025.csv
"""

import csv
import sys
from pathlib import Path

SORTIE = (
    Path(__file__).resolve().parent.parent / "src/demographie/imports/connecteurs/communes_cog.csv"
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    with Path(sys.argv[1]).open(encoding="utf-8") as f:
        communes = sorted(r["COM"] for r in csv.DictReader(f) if r["TYPECOM"] == "COM")
    with SORTIE.open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["commune"])
        ecrivain.writerows([c] for c in communes)
    print(f"{len(communes)} communes -> {SORTIE}")


if __name__ == "__main__":
    main()
