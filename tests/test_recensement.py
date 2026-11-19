"""Recensement : population de 15 ans ou plus par statut d'activité (extrait réel)."""

import json
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import recensement
from demographie.imports.connecteurs.recensement import RECENSEMENT
from demographie.imports.modele import Fichier, Referentiel

JSON = FIXTURES / "DS_RP_EMPLOI_LR_PRINC.json"
client = TestClient(app)


@pytest.fixture(scope="module")
def lignes():
    return list(RECENSEMENT.lire(JSON, Referentiel(identifiants={})))


def test_lecture(lignes):
    (actifs,) = [
        x
        for x in lignes
        if (x.niveau, x.code, x.periode, x.age_max, x.modalite)
        == ("DEP", "75", date(2023, 1, 1), 64, ("statut_activite", "ACTIF"))
    ]
    assert actifs.valeur == Decimal("1152923.46887") and actifs.periode_type == "RP"
    assert {x.code for x in lignes if x.niveau == "FRANCE"} == {"FR", "FM"}
    # Sous-catégories fines (personnes au foyer, autres inactifs) non retenues.
    modalites = {x.modalite[1] for x in lignes if x.modalite}
    assert modalites == {"ACTIF", "ACTIF_OCCUPE", "CHOMEUR", "INACTIF", "RETRAITE", "ETUDIANT",
                         "AUTRE_INACTIF"}  # fmt: skip


def test_telechargement_page_par_page(monkeypatch, tmp_path):
    """L'API renvoie 1000 observations par page : on suit les pages jusqu'à la dernière."""
    appels = []

    def faux_lire_json(url):
        appels.append(url)
        page = int(url.rsplit("page=", 1)[1])
        geo = "2026-DEP-75" if "GEO=DEP" in url else "2026-FRANCE-F"
        dimensions = {"GEO": geo, "AGE": "Y15T64", "EMPSTA_ENQ": "1T2", "SEX": "_T",
                      "EDUC": "_T", "RP_MEASURE": "POP", "FREQ": "A"}  # fmt: skip
        nombre = 1000 if "GEO=DEP" in url and page == 1 else 3
        observations = [
            {"dimensions": {**dimensions, "TIME_PERIOD": str(1000 * page + i)},
             "measures": {"OBS_VALUE_NIVEAU": {"value": 1.5}}}
            for i in range(nombre)
        ]  # fmt: skip
        paging = {"isLast": True} if page > 1 else {}
        return {"observations": observations, "paging": paging}

    monkeypatch.setattr(recensement.telechargement, "lire_json", faux_lire_json)
    monkeypatch.setattr(recensement, "PAUSE", 0)
    chemin = RECENSEMENT.telecharger(RECENSEMENT.fichiers()[0], tmp_path)
    contenu = json.loads(chemin.read_text())
    # 3 niveaux x 2 âges, dont 2 requêtes départementales sur 2 pages.
    assert len(appels) == 8
    assert len(contenu["observations"]) == 4 * 3 + 2 * (1000 + 3)


def test_import_et_api(urls_module):
    fichier = Fichier(url=JSON.resolve().as_uri(), nom=JSON.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, RECENSEMENT, fichier, config.charger().donnees_brutes, chemin_local=JSON
        )
    assert resultat.statut == "PUBLIE", resultat.message

    def serie(indicateur):
        reponse = client.get(
            "/api/v1/series",
            params={"indicateur": indicateur, "niveau": "DEP", "code": "75"},
        ).json()
        return reponse, {v["annee"]: v["valeur"] for v in reponse["valeurs"]}

    taux, valeurs = serie("TAUX_ACTIVITE_15_64")
    assert valeurs == {2012: 77.0, 2017: 78.1, 2023: 78.8}
    assert taux["valeurs"][0]["periode_type"] == "RP"
    assert "5 ans" in taux["indicateur"]["comparabilite"]
    assert serie("ACTIFS_15_64")[1][2023] == 1_152_923
    assert serie("RETRAITES_RP")[1][2023] == 346_028
