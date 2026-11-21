"""Catégories socioprofessionnelles, secteurs et scolarisation (recensement, extraits réels)."""

from datetime import date

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs.recensement import CATEGORIES, SCOLARISATION, SECTEURS
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(identifiants={})
client = TestClient(app)


def _lire(jeu):
    return list(jeu.lire(FIXTURES / jeu.nom_fichier, REFERENTIEL))


def _valeurs(lignes, code, annee):
    return {
        (x.modalite[1] if x.modalite else "TOTAL", x.age_min, x.age_max): x.valeur
        for x in lignes
        if x.code == code and x.periode == date(annee, 1, 1)
    }


def test_categories_socioprofessionnelles():
    france = _valeurs(_lire(CATEGORIES), "FR", 2023)
    # Les 8 groupes font le total des 15 ans ou plus (56,5 millions en 2023).
    groupes = [v for (m, _, _), v in france.items() if m != "TOTAL"]
    assert len(groupes) == 8
    assert round(sum(groupes)) == round(france[("TOTAL", 15, None)]) == 56529157
    assert round(france[("CADRES", 15, None)]) == 6290515


def test_secteurs():
    france = _valeurs(_lire(SECTEURS), "FR", 2023)
    assert round(france[("TOTAL", 15, None)]) == 28841955  # actifs en emploi
    assert round(france[("COMMERCE_SERVICES", 15, None)]) == 13963415


def test_scolarisation():
    lignes = _lire(SCOLARISATION)
    france = _valeurs(lignes, "FR", 2023)
    assert round(france[("SCOLARISE", 18, 24)]) == 2867702
    assert round(france[("TOTAL", 18, 24)]) == 5557276
    assert ("TOTAL", 2, None) not in france  # « 2 ans ou plus » : doublon des tranches
    assert {x.modalite for x in lignes} == {None, ("scolarisation", "SCOLARISE")}


def test_dimension_inattendue(tmp_path):
    chemin = tmp_path / CATEGORIES.nom_fichier
    chemin.write_text(
        '{"observations": [{"dimensions": {"GEO": "2026-DEP-75", "PCS": "3", "SEX": "F",'
        ' "AGE": "Y_GE15", "RP_MEASURE": "POP", "TIME_PERIOD": "2023"},'
        ' "measures": {"OBS_VALUE_NIVEAU": {"value": 1}}}]}'
    )
    with pytest.raises(FichierIllisible, match="SEX"):
        list(CATEGORIES.lire(chemin, REFERENTIEL))


def test_import_et_api(urls_module):
    brut = config.charger().donnees_brutes
    with db.connexion("import") as conn:
        for jeu in (CATEGORIES, SECTEURS, SCOLARISATION):
            chemin = FIXTURES / jeu.nom_fichier
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(conn, jeu, fichier, brut, chemin_local=chemin)
            assert resultat.statut == "PUBLIE", resultat.message

    reponse = client.get(
        "/api/v1/repartition", params={"indicateur": "POP_PCS", "niveau": "FRANCE", "code": "FR"}
    ).json()
    assert reponse["annee"] == 2023 and reponse["periode_type"] == "RP"
    parts = {p["modalite"]: p for p in reponse["parts"]}
    assert list(parts)[0] == "AGRICULTEURS"  # ordre de la nomenclature
    assert parts["CADRES"]["part"] == 11.1  # 6 290 515 / 56 529 157
    assert round(sum(p["part"] for p in parts.values())) == 100

    paris = client.get(
        "/api/v1/repartition",
        params={"indicateur": "EMPLOIS_RP", "niveau": "DEP", "code": "75"},
    ).json()
    assert len(paris["parts"]) == 5

    taux = client.get(
        "/api/v1/series",
        params={"indicateur": "TAUX_SCOLARISATION_18_24", "niveau": "FRANCE", "code": "FR"},
    ).json()
    assert [(v["annee"], v["valeur"]) for v in taux["valeurs"]][-1] == (2023, 51.6)

    inconnu = client.get(
        "/api/v1/repartition", params={"indicateur": "POP", "niveau": "FRANCE", "code": "FR"}
    )
    assert inconnu.status_code == 404

    accueil = client.get("/francais").text
    assert "<strong>Employés</strong> (27 %)" in accueil
    assert "Que faisons-nous ?" not in accueil  # statut d'activité non importé ici
