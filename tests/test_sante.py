"""Personnes prises en charge par groupe de pathologies (export Ameli réel, 2023-2024)."""

from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs.ameli import PATHOLOGIES
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(identifiants={})
client = TestClient(app)


def _lignes():
    return list(PATHOLOGIES.lire(FIXTURES / PATHOLOGIES.nom_fichier, REFERENTIEL))


def _une(lignes, **criteres):
    (ligne,) = [x for x in lignes if all(getattr(x, k) == v for k, v in criteres.items())]
    return ligne.valeur


def test_lecture():
    lignes = _lignes()
    france = {"periode": date(2024, 1, 1), "niveau": "FRANCE", "code": "FR"}
    assert _une(lignes, modalite=None, **france) == 67612360
    assert _une(lignes, modalite=("pathologie", "DIABETE"), **france) == 4471940
    assert _une(lignes, niveau="REG", code="11", modalite=None, periode=date(2024, 1, 1)) == (
        12261580
    )
    corse = {"niveau": "DEP", "code": "2A", "periode": date(2024, 1, 1)}
    assert _une(lignes, modalite=("pathologie", "CANCERS"), **corse) > 0
    assert {x.niveau for x in lignes} == {"FRANCE", "REG", "DEP"}
    assert len({x.modalite for x in lignes}) == 16  # 15 groupes et le total


def test_groupe_inconnu(tmp_path):
    chemin = tmp_path / PATHOLOGIES.nom_fichier
    chemin.write_text("annee;top;region;dept;ntop\n2024;MAT_CAT_INC;11;75;3\n")
    with pytest.raises(FichierIllisible, match="MAT_CAT_INC"):
        list(PATHOLOGIES.lire(chemin, REFERENTIEL))


def test_url_d_export():
    (fichier,) = PATHOLOGIES.fichiers()
    requete = parse_qs(urlparse(fichier.url).query)
    assert requete["where"][0].startswith('cla_age_5="tsage" and sexe=9 and top in ("POP_TOT_IND"')
    assert fichier.url.startswith("https://data.ameli.fr/")


def test_import_et_api(urls_module):
    brut = config.charger().donnees_brutes
    chemin = FIXTURES / PATHOLOGIES.nom_fichier
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(conn, PATHOLOGIES, fichier, brut, chemin_local=chemin)
    assert resultat.statut == "PUBLIE", resultat.message
    france = client.get(
        "/api/v1/repartition",
        params={"indicateur": "PATIENTS_PATHOLOGIE", "niveau": "FRANCE", "code": "FR"},
    ).json()
    assert france["annee"] == 2024 and len(france["parts"]) == 15
    parts = {p["modalite"]: p["part"] for p in france["parts"]}
    assert parts["DIABETE"] == 6.6  # 4 471 940 / 67 612 360
    assert parts["AUCUNE"] == 53.0
