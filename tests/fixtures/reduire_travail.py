"""Fabrique les extraits de test des jeux BDM de l'appli travail.

Extrait réel INSEE (Licence Ouverte 2.0) : Gironde, Paris, Guadeloupe, Mayotte, leurs
régions et la France, observations depuis 2023 seulement.

    uv run python tests/fixtures/reduire_travail.py <fichier complet> <fichier réduit>
"""

import sys
import xml.etree.ElementTree as ET

ZONES = {"D33", "D75", "D971", "D976", "R75", "R11", "FM", "FE", "FR-D976", "DOM", "F_H_IDF"}


def reduire(source: str, cible: str) -> None:
    arbre = ET.parse(source)
    for parent in arbre.getroot().iter():
        for serie in list(parent):
            if not (serie.tag == "Series" or serie.tag.endswith("}Series")):
                continue
            if serie.attrib.get("REF_AREA") not in ZONES:
                parent.remove(serie)
                continue
            for obs in list(serie):
                if obs.attrib.get("TIME_PERIOD", "")[:4] < "2023":
                    serie.remove(obs)
    arbre.write(cible, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
