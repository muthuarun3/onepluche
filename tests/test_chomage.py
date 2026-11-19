"""Taux de chômage localisés (BDM de l'INSEE, extrait réel 2025-2026)."""

from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs.bdm import CHOMAGE
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

XML = FIXTURES / "TAUX-CHOMAGE.xml"
REFERENTIEL = Referentiel(
    identifiants={}, region_du_departement={"75": "11", "92": "11", "971": "01"}
)
client = TestClient(app)


@pytest.fixture(scope="module")
def lignes():
    return list(CHOMAGE.lire(XML, REFERENTIEL))


def _valeur(lignes, niveau, code, periode):
    (ligne,) = [x for x in lignes if (x.niveau, x.code, x.periode) == (niveau, code, periode)]
    return ligne


def test_valeurs_publiees_par_l_insee(lignes):
    # insee.fr/fr/statistiques/2012804, 2e trimestre 2026 (provisoire) et 1er trimestre.
    paris = _valeur(lignes, "DEP", "75", date(2026, 4, 1))
    assert paris.valeur == Decimal("6.6") and paris.statut == "PROVISOIRE"
    assert paris.periode_type == "TRIMESTRE"
    assert _valeur(lignes, "DEP", "75", date(2026, 1, 1)).valeur == Decimal("6.4")
    assert _valeur(lignes, "FRANCE", "FR", date(2026, 4, 1)).valeur == Decimal("8.3")
    assert _valeur(lignes, "DEP", "971", date(2026, 4, 1)).valeur == Decimal("16.4")


def test_territoires(lignes):
    codes = {(x.niveau, x.code) for x in lignes}
    assert ("REG", "01") in codes  # Guadeloupe, reprise de son département
    assert ("REG", "11") in codes and ("FRANCE", "FM") in codes
    assert ("DEP", "976") not in codes  # pas d'estimation pour Mayotte
    assert len({x.periode for x in lignes}) == 6  # 2025-T1 à 2026-T2


def test_xml_dangereux_refuse(tmp_path):
    chemin = tmp_path / "TAUX-CHOMAGE.xml"
    chemin.write_text(
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><x>&b;</x>'
    )
    with pytest.raises(FichierIllisible):
        list(CHOMAGE.lire(chemin, REFERENTIEL))


def test_import_et_api(urls_module):
    fichier = Fichier(url=XML.resolve().as_uri(), nom=XML.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, CHOMAGE, fichier, config.charger().donnees_brutes, chemin_local=XML
        )
    assert resultat.statut == "PUBLIE", resultat.message
    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "TAUX_CHOMAGE", "niveau": "DEP", "code": "75", "debut": 2026},
    ).json()
    assert serie["valeurs"] == [
        {"annee": 2026, "periode": "2026-01-01", "periode_type": "TRIMESTRE",
         "valeur": 6.4, "provisoire": False},
        {"annee": 2026, "periode": "2026-04-01", "periode_type": "TRIMESTRE",
         "valeur": 6.6, "provisoire": True},
    ]  # fmt: skip
    assert "hors Mayotte" in serie["indicateur"]["avertissement"]
