"""Appli travail, PR T4 : contrats courts et temps partiel (recensement 2023, Melodi).

Extrait réel : Gironde, Paris, Guadeloupe, leurs régions et la France ; fabriqué par
tests/fixtures/reduire_dares_bmo.py.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES

from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs.contrats import CONTRATS
from demographie.imports.modele import FichierIllisible, Referentiel

CHEMIN = FIXTURES / CONTRATS.nom_fichier
REFERENTIEL = Referentiel(identifiants={})


def _une(lignes, indicateur, code, sexe="T", age=None):
    (ligne,) = [
        x
        for x in lignes
        if (x.indicateur, x.code, x.sexe, x.age_min) == (indicateur, code, sexe, age)
    ]
    return ligne


def test_parts_par_sexe_et_age():
    lignes = list(CONTRATS.lire(CHEMIN, REFERENTIEL))
    gironde = _une(lignes, "PART_CONTRATS_COURTS", "33")
    assert (gironde.valeur, gironde.periode, gironde.periode_type) == (
        Decimal("15.1"), date(2023, 1, 1), "RP",
    )  # fmt: skip
    assert _une(lignes, "PART_TEMPS_PARTIEL", "33").valeur == Decimal("14.3")
    assert _une(lignes, "PART_TEMPS_PARTIEL", "33", sexe="F").valeur == Decimal("20.4")
    jeunes = _une(lignes, "PART_CONTRATS_COURTS", "33", age=15)
    assert (jeunes.valeur, jeunes.age_max) == (Decimal("50.2"), 24)
    assert _une(lignes, "PART_CONTRATS_COURTS", "33", age=55).age_max is None
    assert _une(lignes, "PART_CONTRATS_COURTS", "FR").valeur == Decimal("15.5")
    assert _une(lignes, "PART_TEMPS_PARTIEL", "FM").valeur > 0
    assert {x.niveau for x in lignes} == {"FRANCE", "REG", "DEP"}
    assert CONTRATS in CONNECTEURS["travail"]


def test_formes_d_emploi_incoherentes(tmp_path):
    contenu = json.loads(CHEMIN.read_text(encoding="utf-8"))
    for obs in contenu["observations"]:
        d = obs["dimensions"]
        if (d["GEO"], d["EMPFORM"], d["WKTIME"]) == ("2026-DEP-33", "1", "_T"):
            obs["measures"]["OBS_VALUE_NIVEAU"]["value"] *= 2
    chemin = tmp_path / CHEMIN.name
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="formes d'emploi"):
        list(CONTRATS.lire(chemin, REFERENTIEL))
