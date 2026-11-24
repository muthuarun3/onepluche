"""Appli travail, PR T2 : demandeurs d'emploi (DARES) et enquête BMO (France Travail).

Extraits réels : Gironde, Paris, Guadeloupe et Mayotte, leurs régions et la France ;
fabriqués par tests/fixtures/reduire_dares_bmo.py.
"""

import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs.bmo import BMO
from demographie.imports.connecteurs.dares import DEMANDEURS
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={"33": "75", "75": "11", "971": "01", "976": "06"},
)
DARES_CSV = FIXTURES / DEMANDEURS.nom_fichier
BMO_XLSX = FIXTURES / "bmo-2026.xlsx"
client = TestClient(app)


def _une(lignes, indicateur, code, periode, sexe="T", age=None, modalite=None):
    (ligne,) = [
        x
        for x in lignes
        if (x.indicateur, x.code, x.periode, x.sexe, x.age_min, x.modalite)
        == (indicateur, code, periode, sexe, age, modalite)
    ]
    return ligne


def test_demandeurs_emploi():
    lignes = list(DEMANDEURS.lire(DARES_CSV, REFERENTIEL))
    t3 = date(2026, 7, 1)
    gironde = _une(lignes, "DEMANDEURS_EMPLOI", "33", t3)
    assert (gironde.valeur, gironde.periode_type, gironde.niveau) == (156520, "TRIMESTRE", "DEP")
    assert _une(lignes, "DEMANDEURS_EMPLOI_A", "33", t3).valeur == 83790
    longue = ("anciennete", "UN_AN_OU_PLUS")
    assert _une(lignes, "DEMANDEURS_EMPLOI", "33", t3, modalite=longue).valeur == 71640
    assert _une(lignes, "PART_LONGUE_DUREE", "33", t3).valeur == Decimal("45.8")
    jeunes = _une(lignes, "DEMANDEURS_EMPLOI", "33", t3, age=0)
    assert jeunes.age_max == 24
    assert _une(lignes, "DEMANDEURS_EMPLOI", "33", t3, age=50).age_max is None
    # Régions (y compris la Guadeloupe) et France, publiées par la DARES.
    niveaux = {(x.niveau, x.code) for x in lignes}
    assert {("REG", "75"), ("REG", "01"), ("FRANCE", "FR"), ("FRANCE", "FM")} <= niveaux
    assert ("DEP", "976") not in niveaux


def test_ventilation_dares_inattendue(tmp_path):
    texte = DARES_CSV.read_text(encoding="utf-8")
    chemin = tmp_path / DARES_CSV.name
    chemin.write_text(texte.replace(";A;Hommes;", ";B;Hommes;", 1), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Ventilation inattendue"):
        list(DEMANDEURS.lire(chemin, REFERENTIEL))


def test_bmo_bassins_additionnes():
    lignes = list(BMO.lire(BMO_XLSX, REFERENTIEL))
    an = date(2026, 1, 1)
    assert _une(lignes, "PROJETS_RECRUTEMENT", "33", an).valeur == 67045
    assert _une(lignes, "RECRUTEMENTS_DIFFICILES", "33", an).valeur == 31577
    assert _une(lignes, "PART_RECRUTEMENTS_DIFFICILES", "33", an).valeur == Decimal("47.1")
    vente = ("famille_metier", "V")
    assert _une(lignes, "PROJETS_RECRUTEMENT", "33", an, modalite=vente).valeur == 26657
    assert _une(lignes, "PART_RECRUTEMENTS_DIFFICILES", "33", an, modalite=vente).valeur == (
        Decimal("46.8")
    )
    agriculteurs = ("metier_bmo", "A0X40")
    assert _une(lignes, "PROJETS_RECRUTEMENT", "33", an, modalite=agriculteurs).valeur == 3840
    # Pas de part par métier : trop de petits effectifs.
    assert not [x for x in lignes if x.indicateur.startswith("PART") and x.modalite == agriculteurs]
    # Mayotte est dans l'enquête ; la France est la somme des départements.
    assert _une(lignes, "PROJETS_RECRUTEMENT", "976", an).valeur == 7908
    france = _une(lignes, "PROJETS_RECRUTEMENT", "FR", an).valeur
    departements = [
        x.valeur
        for x in lignes
        if x.indicateur == "PROJETS_RECRUTEMENT" and x.niveau == "DEP" and x.modalite is None
    ]
    assert france == sum(departements)


def test_bmo_fichiers_xlsx_seulement(monkeypatch):
    ressources = [
        {"title": "Enquête BMO 2026", "url": "https://exemple.fr/Base-open-data-BMO-2026.xlsx"},
        {"title": "Enquête BMO 2025", "url": "https://exemple.fr/Base_open_data_BMO_2025.xlsx"},
        {"title": "Enquête BMO 2024", "url": "https://exemple.fr/Donnees_consolidees_2024.zip"},
    ]
    monkeypatch.setattr(
        "demographie.imports.telechargement.lire_json", lambda url: {"resources": ressources}
    )
    assert [f.nom for f in BMO.fichiers()] == ["bmo-2025.xlsx", "bmo-2026.xlsx"]
    assert BMO.accepte("bmo-2026.xlsx")
    assert CONNECTEURS["travail"][5:7] == (DEMANDEURS, BMO)


def test_import_et_api(urls_module):
    for connecteur, chemin in ((DEMANDEURS, DARES_CSV), (BMO, BMO_XLSX)):
        # Extraits de 3 ou 4 départements : la France ne peut pas égaler leur somme.
        reduit = dataclasses.replace(connecteur, controle_couverture=False, tolerance_sommes=1.0)
        fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
        with db.connexion("import") as conn:
            resultat = pipeline.importer(
                conn, reduit, fichier, config.charger().donnees_brutes, chemin_local=chemin
            )
        assert resultat.statut == "PUBLIE", (chemin.name, resultat.message)

    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "PART_LONGUE_DUREE", "niveau": "DEP", "code": "33", "debut": 2026},
    ).json()
    assert serie["valeurs"][-1]["valeur"] == 45.8
    assert "2025" in serie["indicateur"]["avertissement"]
    indicateurs = client.get(
        "/api/v1/indicateurs", params={"rubrique": "TRAVAIL", "theme": "CHERCHER_CREER"}
    ).json()
    codes = {i["code"] for i in indicateurs}
    assert {"DEMANDEURS_EMPLOI", "PROJETS_RECRUTEMENT", "PART_RECRUTEMENTS_DIFFICILES"} <= codes
