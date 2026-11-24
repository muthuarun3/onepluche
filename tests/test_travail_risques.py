"""Appli travail, PR T5 : télétravail (enquête Emploi, France) et accidents du travail
(Assurance maladie, régions).

Extraits réels : la réponse Melodi complète de la mesure PTREMOTE (2025) ; la sinistralité
par région de 2015, 2023 et 2024.
"""

import re
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES

from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs.risques_travail import ACCIDENTS_TRAVAIL, TELETRAVAIL
from demographie.imports.modele import FichierIllisible, Referentiel

REFERENTIEL = Referentiel(identifiants={})


def test_teletravail():
    lignes = list(TELETRAVAIL.lire(FIXTURES / TELETRAVAIL.nom_fichier, REFERENTIEL))
    par_pcs = {x.modalite[1] if x.modalite else None: x.valeur for x in lignes}
    assert par_pcs == {
        None: Decimal("19.7"),
        "CADRES": Decimal("51.7"),
        "PROF_INTERMEDIAIRES": Decimal("17.0"),
        "EMPLOYES": Decimal("8.2"),
        "OUVRIERS": Decimal("0.2"),
    }
    assert {(x.niveau, x.code, x.periode, x.periode_type) for x in lignes} == {
        ("FRANCE", "FR", date(2025, 1, 1), "ANNEE")
    }
    assert TELETRAVAIL in CONNECTEURS["travail"]


def test_teletravail_sans_total(tmp_path):
    texte = (FIXTURES / TELETRAVAIL.nom_fichier).read_text(encoding="utf-8")
    chemin = tmp_path / TELETRAVAIL.nom_fichier
    chemin.write_text(re.sub(r'"PCS" ?: ?"_T"', '"PCS": "99"', texte), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="ensemble"):
        list(TELETRAVAIL.lire(chemin, REFERENTIEL))


def _une(lignes, indicateur, code, annee):
    (ligne,) = [
        x for x in lignes if (x.indicateur, x.code, x.periode.year) == (indicateur, code, annee)
    ]
    return ligne


def test_accidents_du_travail():
    chemin = FIXTURES / ACCIDENTS_TRAVAIL.nom_fichier
    lignes = list(ACCIDENTS_TRAVAIL.lire(chemin, REFERENTIEL))
    assert _une(lignes, "ACCIDENTS_TRAVAIL", "FR", 2024).valeur == 548550
    assert _une(lignes, "INDICE_FREQUENCE_AT", "FR", 2024).valeur == Decimal("26.4")
    assert _une(lignes, "INDICE_FREQUENCE_AT", "FR", 2015).valeur == Decimal("33.2")
    assert _une(lignes, "INDICE_FREQUENCE_AT", "01", 2024).valeur == Decimal("16.9")
    assert _une(lignes, "ACCIDENTS_TRAJET", "01", 2024).valeur == 257
    assert _une(lignes, "MALADIES_PROFESSIONNELLES", "01", 2024).valeur == 97
    # Mayotte : ses accidents (sommes justes), pas son indice.
    assert _une(lignes, "ACCIDENTS_TRAVAIL", "06", 2024).valeur == 3
    assert not [x for x in lignes if x.code == "06" and x.indicateur == "INDICE_FREQUENCE_AT"]
    regions = sum(
        x.valeur for x in lignes
        if x.indicateur == "ACCIDENTS_TRAVAIL" and x.niveau == "REG" and x.periode.year == 2024
    )  # fmt: skip
    assert regions == 548550
    assert {x.niveau for x in lignes} == {"FRANCE", "REG"}
    assert CONNECTEURS["travail"][-1] is ACCIDENTS_TRAVAIL


def test_accidents_risque_inconnu(tmp_path):
    texte = (FIXTURES / ACCIDENTS_TRAVAIL.nom_fichier).read_text(encoding="utf-8-sig")
    chemin = tmp_path / ACCIDENTS_TRAVAIL.nom_fichier
    chemin.write_text(texte.replace("Accidents de trajet", "Autre risque"), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Risque inattendu"):
        list(ACCIDENTS_TRAVAIL.lire(chemin, REFERENTIEL))
