"""Appli « Les Français sont-ils en sécurité ? » : délinquance enregistrée par la police et
la gendarmerie (base départementale du SSMSI), extrait réel de cinq départements."""

import dataclasses
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import delinquance
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={"23": "75", "75": "11", "93": "11", "2A": "94", "971": "01"},
)
CHEMIN = FIXTURES / delinquance.DELINQUANCE.nom_fichier


def _valeurs():
    return {
        (x.indicateur, x.niveau, x.code, x.periode.year): x.valeur
        for x in delinquance.DELINQUANCE.lire(CHEMIN, REFERENTIEL)
    }


def test_chiffres_du_ssmsi():
    valeurs = _valeurs()
    # Paris : 9 443 cambriolages en 2016, 7 072 en 2025 ; 6 320 violences sexuelles en 2025.
    assert valeurs[("FAITS_CAMBRIOLAGES", "DEP", "75", 2016)] == 9443
    assert valeurs[("FAITS_CAMBRIOLAGES", "DEP", "75", 2025)] == 7072
    assert valeurs[("FAITS_VIOLENCES_SEXUELLES", "DEP", "75", 2025)] == 6320
    assert valeurs[("TAUX_CAMBRIOLAGES", "DEP", "75", 2025)] == Decimal("5.0545976")
    assert {a for (*_x, a) in valeurs} == set(range(2016, 2026))
    # 16 atteintes, en nombre et en taux ; les déclinaisons de l'usage sont ignorées.
    assert len({i for (i, *_x) in valeurs}) == 32


def test_france_et_regions_sommes_des_departements():
    valeurs = _valeurs()
    paris, seine_st_denis = (valeurs[("FAITS_CAMBRIOLAGES", "DEP", d, 2025)] for d in ("75", "93"))
    assert valeurs[("FAITS_CAMBRIOLAGES", "REG", "11", 2025)] == paris + seine_st_denis
    fr = valeurs[("FAITS_HOMICIDES", "FRANCE", "FR", 2025)]
    fm = valeurs[("FAITS_HOMICIDES", "FRANCE", "FM", 2025)]
    assert fr - fm == valeurs[("FAITS_HOMICIDES", "DEP", "971", 2025)]
    # Taux régional = somme des faits / somme des logements, pas moyenne des taux.
    taux = valeurs[("TAUX_CAMBRIOLAGES", "REG", "11", 2025)]
    assert valeurs[("TAUX_CAMBRIOLAGES", "DEP", "75", 2025)] < taux
    assert taux < valeurs[("TAUX_CAMBRIOLAGES", "DEP", "93", 2025)]


def _modifie(tmp_path, ancien, nouveau):
    chemin = tmp_path / CHEMIN.name
    chemin.write_text(CHEMIN.read_text(encoding="utf-8-sig").replace(ancien, nouveau, 1))
    return chemin


def test_unite_de_compte_changee(tmp_path):
    chemin = _modifie(tmp_path, '"Homicides";"Victime"', '"Homicides";"Infraction"')
    with pytest.raises(FichierIllisible, match="unité de compte"):
        list(delinquance.DELINQUANCE.lire(chemin, REFERENTIEL))


def test_indicateur_renomme(tmp_path):
    chemin = tmp_path / CHEMIN.name
    texte = CHEMIN.read_text(encoding="utf-8-sig")
    chemin.write_text(texte.replace('"Vols avec armes"', '"Vols armés"'))
    with pytest.raises(FichierIllisible, match="Indicateurs absents : Vols avec armes"):
        list(delinquance.DELINQUANCE.lire(chemin, REFERENTIEL))


def test_colonne_absente(tmp_path):
    chemin = _modifie(tmp_path, '"taux_pour_mille"', '"taux"')
    with pytest.raises(FichierIllisible, match="taux_pour_mille"):
        list(delinquance.DELINQUANCE.lire(chemin, REFERENTIEL))


def test_import_publie(urls_module):
    connecteur = dataclasses.replace(delinquance.DELINQUANCE, controle_couverture=False)
    fichier = Fichier(url=CHEMIN.resolve().as_uri(), nom=CHEMIN.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=CHEMIN
        )
    assert resultat.statut == "PUBLIE", resultat.message
    serie = client.get(
        "/api/v1/series", params={"indicateur": "FAITS_CAMBRIOLAGES", "niveau": "DEP", "code": "75"}
    ).json()
    assert [v["valeur"] for v in serie["valeurs"]][-1] == 7072
    indicateurs = client.get("/api/v1/indicateurs", params={"rubrique": "SECURITE"}).json()
    assert len(indicateurs) == 32
    assert {i["theme"] for i in indicateurs} == {"PERSONNES", "VOLS", "BIENS", "STUPEFIANTS"}
