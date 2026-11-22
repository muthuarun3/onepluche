"""Appli « Les Français sont-ils en sécurité ? » : accidents de la route (ONISR, fichiers
BAAC) et sentiment d'insécurité (enquêtes CVS et VRS), extraits réels."""

import dataclasses
import zipfile
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import EstimationsDepartements, ressenti, routes
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel(
    identifiants={}, region_du_departement={"23": "75", "2A": "94", "971": "01"}
)


def _routes(annee):
    chemin = FIXTURES / f"accidents-{annee}.zip"
    return {
        (x.indicateur, x.niveau, x.code, x.periode.year): x.valeur
        for x in routes.ACCIDENTS.lire(chemin, REFERENTIEL)
    }


def test_departements_des_deux_formats():
    assert routes.departement("590") == "59"
    assert routes.departement("201") == "2A"
    assert routes.departement("971") == "971"
    assert routes.departement("2B") == "2B"
    assert routes.departement("977") is None  # Saint-Barthélemy
    with pytest.raises(FichierIllisible):
        routes.departement("99")


def test_tues_et_blesses_ancien_format():
    # Fichiers 2016 complets : 3 655 tués en France, 3 477 en métropole (chiffres ONISR).
    valeurs = _routes(2016)
    assert valeurs[("TUES_ROUTE", "DEP", "23", 2016)] == 5
    assert valeurs[("TUES_ROUTE", "DEP", "2A", 2016)] == 14
    assert valeurs[("BLESSES_HOSPITALISES_ROUTE", "DEP", "971", 2016)] == 246
    assert valeurs[("TUES_ROUTE", "FRANCE", "FR", 2016)] == 5 + 14 + 57
    assert valeurs[("TUES_ROUTE", "FRANCE", "FM", 2016)] == 5 + 14


def test_nouveau_format_sans_collectivites_d_outre_mer():
    valeurs = _routes(2025)
    assert valeurs[("TUES_ROUTE", "DEP", "2A", 2025)] == 10
    assert valeurs[("TUES_ROUTE", "DEP", "971", 2025)] == 49
    assert {c for (_i, n, c, _a) in valeurs if n == "DEP"} == {"23", "2A", "971"}


def test_archive_incomplete(tmp_path):
    chemin = tmp_path / "accidents-2025.zip"
    with zipfile.ZipFile(chemin, "w") as archive:
        archive.writestr("usagers.csv", "Num_Acc;grav\n")
    with pytest.raises(FichierIllisible, match="caracteristiques.csv absent"):
        list(routes.ACCIDENTS.lire(chemin, REFERENTIEL))


def test_sentiment_d_insecurite_cvs():
    lignes = list(ressenti.CVS.lire(FIXTURES / ressenti.CVS.nom_fichier, REFERENTIEL))
    valeurs = {(x.indicateur, x.periode.year): x.valeur for x in lignes}
    assert valeurs[("PART_INSECURITE_QUARTIER", 2007)] == Decimal("10.9")
    assert valeurs[("PART_INSECURITE_DOMICILE", 2008)] == Decimal("6.6")
    assert {a for (_i, a) in valeurs} == set(range(2007, 2020))
    assert {(x.niveau, x.code) for x in lignes} == {("FRANCE", "FM")}
    assert len(lignes) == 3 * 13  # ventilations (taille d'agglomération) ignorées


def test_vrs_recopie_avec_sa_source():
    valeurs = {
        (x.indicateur, x.periode.year): x.valeur
        for x in ressenti.VRS_RAPPORTS.lire(ressenti.VRS, REFERENTIEL)
    }
    assert valeurs[("PART_INSECURITE_QUARTIER", 2024)] == 22
    assert valeurs[("PART_RENONCE_SORTIR", 2022)] == 18


def test_vrs_sans_source(tmp_path):
    chemin = tmp_path / "vrs.csv"
    chemin.write_text("indicateur;annee;valeur;champ;source\nPART_INSECURITE_DOMICILE;2025;14;x;\n")
    with pytest.raises(FichierIllisible, match="Source manquante"):
        list(ressenti.VRS_RAPPORTS.lire(chemin, REFERENTIEL))


def _importer(connecteur, chemin):
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_taux_par_million(urls_module):
    resultat = _importer(
        EstimationsDepartements(), FIXTURES / "estim-pop-dep-sexe-aq-1975-2026.xlsx"
    )
    assert resultat.statut == "PUBLIE", resultat.message
    accidents = dataclasses.replace(routes.ACCIDENTS, controle_couverture=False)
    for chemin in (FIXTURES / "accidents-2016.zip", FIXTURES / "accidents-2025.zip"):
        resultat = _importer(accidents, chemin)
        assert resultat.statut == "PUBLIE", resultat.message
    for connecteur, chemin in (
        (ressenti.CVS, FIXTURES / ressenti.CVS.nom_fichier),
        (ressenti.VRS_RAPPORTS, ressenti.VRS),
    ):
        resultat = _importer(connecteur, chemin)
        assert resultat.statut == "PUBLIE", resultat.message

    def serie(indicateur, niveau="DEP", code="23"):
        reponse = client.get(
            "/api/v1/series", params={"indicateur": indicateur, "niveau": niveau, "code": code}
        )
        return {v["annee"]: v["valeur"] for v in reponse.json()["valeurs"]}

    # Creuse : 5 tués en 2025 pour environ 115 000 habitants, soit environ 43 par million.
    taux = serie("TAUX_TUES_ROUTE")
    assert 35 < taux[2025] < 50
    assert serie("TUES_ROUTE")[2016] == 5
    ressenti_fm = serie("PART_INSECURITE_QUARTIER", "FRANCE", "FM")
    assert ressenti_fm[2019] < ressenti_fm[2024] == 22
    assert 2020 not in ressenti_fm and 2021 not in ressenti_fm
