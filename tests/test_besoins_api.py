"""Appli 2, phase D : API (filtres rubrique et thème, fiche d'un territoire)."""

import dataclasses

from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import EstimationsDepartements, soins
from demographie.imports.modele import Fichier

client = TestClient(app)


def test_indicateurs_filtres(urls_db):
    tous = client.get("/api/v1/indicateurs").json()
    besoins = client.get("/api/v1/indicateurs", params={"rubrique": "BESOINS"}).json()
    soins_ = client.get("/api/v1/indicateurs", params={"theme": "SOINS"}).json()
    assert len(tous) > len(besoins) > len(soins_) > 0
    assert {i["rubrique"] for i in besoins} == {"BESOINS"}
    assert {i["theme"] for i in soins_} == {"SOINS"}
    assert "APL_MG" in {i["code"] for i in soins_}
    # Même forme qu'avant : une liste de définitions.
    assert set(tous[0]) == set(besoins[0])


def test_filtre_inconnu_refuse(urls_db):
    assert client.get("/api/v1/indicateurs", params={"theme": "CINEMA"}).status_code == 422
    assert client.get("/api/v1/fiche", params={"niveau": "DEP", "code": "999"}).status_code in (
        404,
        422,
    )


def _importer(connecteur, nom):
    chemin = FIXTURES / nom
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_fiche(urls_module):
    apl = dataclasses.replace(soins.APL_MEDECINS, communes_min=100, controle_couverture=False)
    etapes = [
        (EstimationsDepartements(), "estim-pop-dep-sexe-aq-1975-2026.xlsx"),
        (apl, apl.nom_fichier),
        (soins.ALD_SANS_MEDECIN_TRAITANT, soins.ALD_SANS_MEDECIN_TRAITANT.nom_fichier),
        (soins.PHARMACIES, soins.PHARMACIES.nom_fichier),
    ]
    for connecteur, nom in etapes:
        resultat = _importer(connecteur, nom)
        assert resultat.statut == "PUBLIE", resultat.message

    fiche = client.get(
        "/api/v1/fiche", params={"niveau": "DEP", "code": "23", "theme": "SOINS"}
    ).json()
    assert fiche["territoire"]["libelle"] == "Creuse"
    lignes = {x["indicateur"]["code"]: x for x in fiche["lignes"]}
    assert set(lignes) == {
        "APL_MG",
        "PART_POP_APL_MG_FAIBLE",
        "ALD_SANS_MT",
        "PHARMACIES",
        "PHARMACIES_10000",
    }
    ald = lignes["ALD_SANS_MT"]
    assert (ald["annee"], ald["valeur"]) == (2025, 9.6)
    assert ald["france"] == {"code": "FR", "valeur": 4.3, "provisoire": False}
    assert ald["indicateur"]["source_code"] == "CNAM_ACCES"
    assert lignes["APL_MG"]["annee"] == 2024
    # Accès avant manque.
    angles = [x["indicateur"]["angle"] for x in fiche["lignes"] if x["indicateur"]["angle"]]
    assert angles == sorted(angles, key=["ACCES", "COUT", "MANQUE"].index)

    # Sans thème : toute la rubrique BESOINS ; rubrique QUI : la population.
    besoins = client.get("/api/v1/fiche", params={"niveau": "DEP", "code": "23"}).json()
    assert len(besoins["lignes"]) == len(fiche["lignes"])
    qui = client.get(
        "/api/v1/fiche", params={"niveau": "DEP", "code": "23", "rubrique": "QUI"}
    ).json()
    assert "POP" in {x["indicateur"]["code"] for x in qui["lignes"]}
    assert "APL_MG" not in {x["indicateur"]["code"] for x in qui["lignes"]}
