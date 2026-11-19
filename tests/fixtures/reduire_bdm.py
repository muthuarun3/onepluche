"""Fabrique un extrait de test d'un jeu BDM (SDMX-ML) : trimestres 2025 et 2026 seulement.

Extrait réel INSEE (Licence Ouverte 2.0) : mêmes séries, moins d'observations.

    uv run python tests/fixtures/reduire_bdm.py <fichier complet> <fichier réduit>
"""

import sys
import xml.etree.ElementTree as ET


def reduire(source: str, cible: str) -> None:
    arbre = ET.parse(source)
    for serie in arbre.getroot().iter():
        if serie.tag == "Series" or serie.tag.endswith("}Series"):
            for obs in list(serie):
                if obs.attrib.get("TIME_PERIOD", "")[:4] not in ("2025", "2026"):
                    serie.remove(obs)
    arbre.write(cible, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    reduire(sys.argv[1], sys.argv[2])
