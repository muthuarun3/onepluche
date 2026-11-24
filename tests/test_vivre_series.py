"""Appli 3, phase A2 : séries nationales de la rubrique VIVRE (extraits Melodi réels)."""

import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS, vivre
from demographie.imports.modele import Fichier, Referentiel

REFERENTIEL = Referentiel(identifiants={})
client = TestClient(app)


def _lignes(jeu):
    return list(jeu.lire(FIXTURES / jeu.nom_fichier, REFERENTIEL))


def _valeur(lignes, indicateur, annee, **criteres):
    (ligne,) = [
        x
        for x in lignes
        if x.indicateur == indicateur
        and x.periode == date(annee, 1, 1)
        and all(getattr(x, k) == v for k, v in criteres.items())
    ]
    return ligne


def test_salaire_moyen_depuis_1996():
    lignes = _lignes(vivre.SALAIRE_SERIE)
    # Euros constants de 2024 : la dernière année vaut le salaire de la Base Tous salariés.
    assert _valeur(lignes, "SALAIRE_PRIVE_SERIE", 2024, sexe="T").valeur == 2733
    assert _valeur(lignes, "SALAIRE_PRIVE_SERIE", 2024, sexe="F").valeur == 2514
    assert _valeur(lignes, "SALAIRE_PRIVE_SERIE", 1996, sexe="T").valeur == 2400
    assert {(x.niveau, x.code) for x in lignes} == {("FRANCE", "FR")}


def test_niveau_de_vie_et_inegalites_en_metropole():
    lignes = _lignes(vivre.NIVEAU_VIE_SERIES)
    assert {x.code for x in lignes} == {"FM"}
    assert _valeur(lignes, "TAUX_PAUVRETE_SERIE", 2023).valeur == Decimal("15.4")
    assert _valeur(lignes, "GINI_SERIE", 2023).valeur == Decimal("0.297")
    assert _valeur(lignes, "RAPPORT_D9_D1_SERIE", 1996).valeur == Decimal("3.51")
    assert {x.indicateur for x in lignes} == {
        "NIVEAU_VIE_MEDIAN_SERIE", "TAUX_PAUVRETE_SERIE", "GINI_SERIE", "RAPPORT_D9_D1_SERIE",
    }  # fmt: skip


def test_comptes_des_menages():
    epargne = _lignes(vivre.TAUX_EPARGNE)
    # Critère de fin de la phase A2 (dossier) : taux d'épargne 2025 = 17,9 %, provisoire.
    taux_2025 = _valeur(epargne, "TAUX_EPARGNE", 2025)
    assert taux_2025.valeur == Decimal("17.908") and taux_2025.statut == "PROVISOIRE"
    assert _valeur(epargne, "TAUX_EPARGNE", 2010).statut == "DEFINITIF"
    # Une baisse du pouvoir d'achat est une valeur négative, admise par la borne basse.
    pouvoir = _lignes(vivre.POUVOIR_ACHAT)
    assert _valeur(pouvoir, "POUVOIR_ACHAT_UC", 2025).valeur == Decimal("-0.688")
    rdb = _lignes(vivre.REVENU_DISPONIBLE)
    assert _valeur(rdb, "REVENU_DISPONIBLE", 2025).valeur == Decimal("1876862.7")
    assert _lignes(vivre.TAUX_EPARGNE_FINANCIERE)


def test_placements_financiers():
    lignes = _lignes(vivre.PATRIMOINE_FINANCIER)
    en_2024 = {
        (x.modalite[1] if x.modalite else "TOTAL"): x.valeur
        for x in lignes
        if x.periode == date(2024, 1, 1)
    }
    assert en_2024["TOTAL"] == Decimal("6966536.6")
    assert en_2024["ASSURANCE_VIE"] == Decimal("1859238.2")
    assert set(en_2024) == {
        "TOTAL",
        "DEPOTS",
        "TITRES_CREANCE",
        "ACTIONS",
        "FONDS",
        "ASSURANCE_VIE",
    }
    # Le total couvre aussi des placements non détaillés (assurance dommages, crédits…).
    assert en_2024["TOTAL"] > sum(v for k, v in en_2024.items() if k != "TOTAL")


def test_patrimoine_par_age_categorie_et_niveau_de_vie():
    ages = _lignes(vivre.PATRIMOINE_AGES)
    # Enquête 2024, France hors Mayotte, rangée sous la France.
    assert {(x.niveau, x.code) for x in ages} == {("FRANCE", "FR")}
    assert _valeur(ages, "PATRIMOINE_BRUT_MOYEN", 2024, age_min=None).valeur == 374900
    assert _valeur(ages, "PATRIMOINE_BRUT_MOYEN", 2024, age_min=0).valeur == 104400
    assert _valeur(ages, "PATRIMOINE_NET_MEDIAN", 2024).valeur == 148100
    categories = {x.modalite[1]: x.valeur for x in _lignes(vivre.PATRIMOINE_CATEGORIES)}
    assert len(categories) == 12  # sans le total, déjà lu avec les âges
    assert categories["CADRES_HORS_LIBERALES"] == 603700
    deciles = {x.modalite[1]: x.valeur for x in _lignes(vivre.PATRIMOINE_DECILES)}
    assert sorted(deciles) == [f"D{i:02d}" for i in range(1, 11)]
    assert deciles["D10"] == 1373100


def test_groupe_vivre():
    assert CONNECTEURS["vivre"][3:] == vivre.SERIES_NATIONALES


def test_import_et_api(urls_module):
    brut = config.charger().donnees_brutes
    with db.connexion("import") as conn:
        for jeu in vivre.SERIES_NATIONALES:
            jeu = dataclasses.replace(jeu, controle_couverture=False)
            chemin = FIXTURES / jeu.nom_fichier
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(conn, jeu, fichier, brut, chemin_local=chemin)
            assert resultat.statut == "PUBLIE", (jeu.nom_fichier, resultat.message)

    epargne = client.get(
        "/api/v1/indicateurs", params={"rubrique": "VIVRE", "theme": "EPARGNE"}
    ).json()
    assert {i["code"] for i in epargne} == {"TAUX_EPARGNE", "TAUX_EPARGNE_FINANCIERE"}
    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "TAUX_EPARGNE", "niveau": "FRANCE", "code": "FR", "debut": 2024},
    ).json()
    assert [(v["annee"], v["valeur"]) for v in serie["valeurs"]] == [
        (2024, pytest.approx(18.514)), (2025, pytest.approx(17.908)),
    ]  # fmt: skip
    pauvrete = client.get(
        "/api/v1/series",
        params={"indicateur": "TAUX_PAUVRETE_SERIE", "niveau": "FRANCE", "code": "FM"},
    ).json()
    assert "Filosofi" in pauvrete["indicateur"]["comparabilite"]
