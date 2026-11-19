"""Lecture des fichiers d'estimations INSEE (extraits réels, voir fixtures/reduire.py)."""

from collections import Counter
from datetime import date

import openpyxl
import pytest
from conftest import FIXTURES

from demographie.imports.connecteurs.estimations import (
    EstimationsDepartements,
    EstimationsRegions,
    normaliser,
)
from demographie.imports.modele import FichierIllisible, Referentiel

FICHIER_DEP = FIXTURES / "estim-pop-dep-sexe-aq-1975-2026.xlsx"
FICHIER_REG = FIXTURES / "estim-pop-nreg-sexe-aq-1975-2026.xlsx"
REGIONS = {
    "01": "Guadeloupe", "02": "Martinique", "03": "Guyane", "04": "La Réunion",
    "06": "Mayotte", "11": "Île-de-France", "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté", "28": "Normandie", "32": "Hauts-de-France",
    "44": "Grand Est", "52": "Pays de la Loire", "53": "Bretagne",
    "75": "Nouvelle-Aquitaine", "76": "Occitanie", "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur", "94": "Corse",
}  # fmt: skip
REFERENTIEL = Referentiel(identifiants={}, libelles_regions=REGIONS)


@pytest.fixture(scope="module")
def lignes_dep():
    return list(EstimationsDepartements().lire(FICHIER_DEP, REFERENTIEL))


def _valeur(lignes, code, annee, sexe="T", age_min=None, age_max=None):
    (trouve,) = [
        ligne.valeur
        for ligne in lignes
        if (ligne.code, ligne.periode.year, ligne.sexe, ligne.age_min, ligne.age_max)
        == (code, annee, sexe, age_min, age_max)
    ]
    return trouve


def test_normaliser():
    assert normaliser("Centre-Val-de-Loire") == normaliser("Centre-Val de Loire")
    assert normaliser("Île-de-France ") == "iledefrance"


def test_reconnait_ses_fichiers():
    assert EstimationsDepartements().accepte("estim-pop-dep-sexe-aq-1975-2027.xlsx")
    assert not EstimationsDepartements().accepte("estim-pop-nreg-sexe-aq-1975-2026.xlsx")
    assert EstimationsRegions().accepte("estim-pop-nreg-sexe-aq-1975-2026.xlsx")
    assert not EstimationsRegions().accepte("estim-pop-dep-sexe-gca-1975-2026.xlsx")


def test_territoires_lus(lignes_dep):
    par_annee = Counter()
    for annee, _code in {(ligne.periode.year, ligne.code) for ligne in lignes_dep}:
        par_annee[annee] += 1
    # 101 départements + France + France métropolitaine ; en 1995, 4 DOM (pas Mayotte) ;
    # en 1975 la métropole seulement (96 départements + France métropolitaine).
    assert par_annee == {2026: 103, 2025: 103, 2024: 103, 1995: 102, 1975: 97}
    codes = {ligne.code for ligne in lignes_dep}
    assert {"2A", "2B", "971", "976", "FR", "FM"} <= codes
    assert "DOM" not in codes


def test_valeurs_publiees_par_l_insee(lignes_dep):
    assert _valeur(lignes_dep, "75", 2026) == 2_047_602
    assert _valeur(lignes_dep, "23", 2026) == 114_943
    assert _valeur(lignes_dep, "FR", 2026) == 69_081_996
    assert _valeur(lignes_dep, "FM", 1975) == 52_600_000
    assert _valeur(lignes_dep, "75", 2026, "H") + _valeur(lignes_dep, "75", 2026, "F") == 2_047_602


def test_tranches_d_age(lignes_dep):
    tranches_2026 = {
        (ligne.age_min, ligne.age_max)
        for ligne in lignes_dep
        if ligne.code == "75" and ligne.periode == date(2026, 1, 1)
    }
    assert len(tranches_2026) == 21  # 20 tranches de 5 ans + total
    assert (95, None) in tranches_2026 and (None, None) in tranches_2026
    # 1990-1998 : les DOM s'arrêtent à « 90 ans et plus ».
    tranches_971 = {
        (ligne.age_min, ligne.age_max)
        for ligne in lignes_dep
        if ligne.code == "971" and ligne.periode.year == 1995
    }
    assert (90, None) in tranches_971 and (90, 94) not in tranches_971


def test_trois_dernieres_annees_provisoires(lignes_dep):
    statuts = {(ligne.periode.year, ligne.statut) for ligne in lignes_dep}
    assert statuts == {
        (2026, "PROVISOIRE"),
        (2025, "PROVISOIRE"),
        (2024, "PROVISOIRE"),
        (1995, "DEFINITIF"),
        (1975, "DEFINITIF"),
    }


def test_regions_rapprochees_par_libelle():
    lignes = list(EstimationsRegions().lire(FICHIER_REG, REFERENTIEL))
    codes_2026 = {(ligne.niveau, ligne.code) for ligne in lignes if ligne.periode.year == 2026}
    assert codes_2026 == {("REG", c) for c in REGIONS} | {("FRANCE", "FR"), ("FRANCE", "FM")}
    assert _valeur(lignes, "24", 2026) == 2_589_286  # « Centre-Val-de-Loire » dans le fichier


def test_libelle_inconnu_transmis_tel_quel(tmp_path):
    classeur = openpyxl.load_workbook(FICHIER_REG)
    feuille = classeur["2026"]
    for rang in feuille.iter_rows(min_col=1, max_col=1):
        if rang[0].value == "Bretagne":
            rang[0].value = "Armorique"
    chemin = tmp_path / "estim-pop-nreg-sexe-aq-1975-2026.xlsx"
    classeur.save(chemin)
    codes = {ligne.code for ligne in EstimationsRegions().lire(chemin, REFERENTIEL)}
    assert "Armorique" in codes


def test_structure_inattendue_refusee(tmp_path):
    classeur = openpyxl.Workbook()
    classeur.active.title = "2026"
    classeur.active.append(["Année 2026"])
    classeur.active.append(["Départements", None, "Total"])
    classeur.active.append(["75", "Paris", 2_047_602])
    chemin = tmp_path / "estim-pop-dep-sexe-aq-1975-2026.xlsx"
    classeur.save(chemin)
    with pytest.raises(FichierIllisible):
        list(EstimationsDepartements().lire(chemin, REFERENTIEL))
