"""Extraits de test des jeux Melodi de l'appli 3.

Télécharge le jeu par l'API, comme le connecteur, puis réduit le fichier :

- Filosofi détaillé, salaires BTS : quelques territoires seulement (Creuse, Paris,
  La Réunion, Guadeloupe absente de Filosofi, Nouvelle-Aquitaine, France) ;
- séries nationales : les mesures et ventilations lues par le connecteur, pour 1996, 2010
  et depuis 2019.

    uv run python tests/fixtures/reduire_vivre.py
"""

import json
from pathlib import Path

from demographie.imports.connecteurs import vivre

GARDES = {"DEP-23", "DEP-75", "DEP-974", "DEP-971", "REG-75", "FRANCE-F", "FRANCE-FM"}
DOSSIER = Path(__file__).parent


def reduire(jeu) -> None:
    chemin = jeu.telecharger(jeu.fichiers()[0], DOSSIER)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    chemin.unlink()
    contenu["observations"] = [
        o for o in contenu["observations"] if o["dimensions"]["GEO"].split("-", 1)[1] in GARDES
    ]
    (DOSSIER / jeu.nom_fichier).write_text(
        json.dumps(contenu, sort_keys=True, ensure_ascii=False, indent=0), encoding="utf-8"
    )


def _lue(jeu, dim: dict) -> bool:
    if dim.get(jeu.dimension_mesure) not in jeu.mesures:
        return False
    if jeu.dimension and dim.get(jeu.dimension) not in jeu.modalites:
        return False
    annee = int(dim["TIME_PERIOD"])
    return annee in (1996, 2010) or annee >= 2019


def reduire_national(jeu) -> None:
    chemin = jeu.telecharger(jeu.fichiers()[0], DOSSIER)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    chemin.unlink()
    contenu["observations"] = [o for o in contenu["observations"] if _lue(jeu, o["dimensions"])]
    (DOSSIER / jeu.nom_fichier).write_text(
        json.dumps(contenu, sort_keys=True, ensure_ascii=False, indent=0), encoding="utf-8"
    )


if __name__ == "__main__":
    for jeu in (vivre.REVENUS_FILOSOFI, vivre.SALAIRES_CATEGORIES, vivre.SALAIRES_AGES):
        reduire(jeu)
    for jeu in vivre.SERIES_NATIONALES:
        reduire_national(jeu)
