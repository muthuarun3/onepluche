"""Appli « Où va l'argent public ? », budget de l'État : situation mensuelle budgétaire
(janvier 2024 à septembre 2026) et crédits par mission des PLRG 2023 à 2025."""

import json
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline, telechargement
from demographie.imports.connecteurs import CONNECTEURS, etat
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel(identifiants={}, region_du_departement={})
MENSUEL = FIXTURES / etat.SITUATION_MENSUELLE.nom_fichier


def _mensuel(chemin=MENSUEL):
    return {
        (x.indicateur, x.modalite[1] if x.modalite else None, x.periode): x
        for x in etat.SITUATION_MENSUELLE.lire(chemin, REFERENTIEL)
    }


def test_situation_mensuelle():
    v = _mensuel()
    # Fin 2025 : déficit de 124,2 Md€ ; fin septembre 2026 : 159,2 Md€.
    assert v[("SOLDE_ETAT", None, date(2025, 12, 1))].valeur == Decimal("-124.205674")
    assert v[("SOLDE_ETAT", None, date(2026, 9, 1))].valeur == Decimal("-159.172976")
    # L'arrêté d'avril 2024 est daté du 24 : rangé au 1er avril.
    assert ("SOLDE_ETAT", None, date(2024, 4, 1)) in v
    tva = v[("RECETTES_FISCALES_ETAT", "TVA", date(2025, 12, 1))].valeur
    assert tva == Decimal("98.067166")
    total = v[("RECETTES_FISCALES_ETAT", None, date(2025, 12, 1))].valeur
    parts = [v[("RECETTES_FISCALES_ETAT", m, date(2025, 12, 1))].valeur
             for m in ("IR", "IS", "TICPE", "TVA", "AUTRES")]  # fmt: skip
    assert abs(sum(parts) - total) < Decimal("0.00001")
    assert v[("SOLDE_ETAT", None, date(2026, 9, 1))].statut == "PROVISOIRE"
    assert v[("SOLDE_ETAT", None, date(2025, 9, 1))].statut == "DEFINITIF"


def test_ligne_absente(tmp_path):
    lignes = json.loads(MENSUEL.read_text(encoding="utf-8"))
    lignes = [x for x in lignes if x["ligne_d_information"] != "Taxe sur la valeur ajoutée"]
    chemin = tmp_path / MENSUEL.name
    chemin.write_text(json.dumps(lignes), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="RECETTES_FISCALES_ETAT TVA"):
        list(etat.SITUATION_MENSUELLE.lire(chemin, REFERENTIEL))


def test_credits_par_mission():
    lignes = list(etat.CREDITS_MISSIONS.lire(FIXTURES / "plrg-credits-2025.csv", REFERENTIEL))
    v = {(x.indicateur, x.modalite[1] if x.modalite else None): x.valeur for x in lignes}
    assert v[("CREDITS_VOTES", None)] == Decimal("582.396983")
    assert v[("CREDITS_CONSOMMES", "DEFENSE")] == Decimal("62.123737")
    # « Travail et emploi », renommée en 2025, garde son code.
    assert ("CREDITS_VOTES", "TRAVAIL_EMPLOI") in v
    missions = [x for x in lignes if x.indicateur == "CREDITS_VOTES" and x.modalite]
    assert len(missions) == 33
    assert all(x.periode == date(2025, 1, 1) for x in lignes)


def test_colonne_absente(tmp_path):
    chemin = tmp_path / "plrg-credits-2025.csv"
    texte = (FIXTURES / "plrg-credits-2025.csv").read_text(encoding="utf-8-sig")
    chemin.write_text(texte.replace("Depenses_constatees", "Depenses"), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Depenses_constatees"):
        list(etat.CREDITS_MISSIONS.lire(chemin, REFERENTIEL))


def test_decouverte_des_plrg(monkeypatch):
    base = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
    reponse = {"results": [
        {"dataset_id": "plrg-2024", "attachments": [
            {"title": "Annexe1-Etat_AE-2024.csv", "url": f"{base}/plrg-2024/attachments/ae"},
            {"title": "Annexe1-Etat_CP-2024.csv", "url": f"{base}/plrg-2024/attachments/cp"},
        ]},
        {"dataset_id": "plr-2019", "attachments": [
            {"title": "Annexe1-Etat_CP-2019.csv", "url": f"{base}/plr-2019/attachments/cp"},
        ]},
    ]}  # fmt: skip
    monkeypatch.setattr(telechargement, "lire_page", lambda _url: json.dumps(reponse))
    (fichier,) = etat.CREDITS_MISSIONS.fichiers()
    assert fichier.nom == "plrg-credits-2024.csv"
    assert fichier.url.endswith("/plrg-2024/attachments/cp")


def test_import_et_page(urls_module):
    connecteurs = (etat.SITUATION_MENSUELLE, etat.CREDITS_MISSIONS)
    assert all(c in CONNECTEURS["argent"] for c in connecteurs)
    with db.connexion("import") as conn:
        for connecteur, nom in [
            (etat.SITUATION_MENSUELLE, etat.SITUATION_MENSUELLE.nom_fichier),
            *((etat.CREDITS_MISSIONS, f"plrg-credits-{a}.csv") for a in (2023, 2024, 2025)),
        ]:
            chemin = FIXTURES / nom
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=nom)
            resultat = pipeline.importer(
                conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
            )
            assert resultat.statut == "PUBLIE", resultat.message

    page = client.get("/argent-public/etat")
    assert page.status_code == 200
    texte = page.text
    assert "Fin septembre 2026" in texte
    assert "159 Md€" in texte  # déficit cumulé fin septembre 2026
    assert "contre 155 Md€ à la même date en 2025" in texte
    assert "Les missions de l'État en 2025" in texte
    assert "Remboursements et dégrèvements" in texte
    assert 'id="solde-etat"' in texte
    ancienne = client.get("/argent-public/etat", params={"annee": 2023}).text
    assert "Les missions de l'État en 2023" in ancienne
    assert client.get("/argent-public/etat", params={"annee": 1900}).status_code == 422
    assert "/argent-public/etat" in client.get("/argent-public").text


def test_page_sans_donnees(urls_db):
    page = client.get("/argent-public/etat")
    assert page.status_code == 200
    assert "pas encore importé" in page.text
