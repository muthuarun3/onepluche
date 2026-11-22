"""Appli 5, phase A : projections de population (INSEE Omphale 2022 et projections
nationales de 2026), publiées dans stat.projection."""

import dataclasses
from datetime import date

from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import (
    CONNECTEURS,
    PROJECTIONS_DEPARTEMENTALES,
    PROJECTIONS_FRANCE,
)
from demographie.imports.connecteurs.omphale import tranche
from demographie.imports.modele import Fichier, Referentiel

# Les fichiers de test ne gardent que six départements (tests/fixtures/reduire_omphale.py).
OMPHALE = dataclasses.replace(PROJECTIONS_DEPARTEMENTALES, departements_attendus=6)
REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={
        "01": "84",
        "2A": "94",
        "23": "75",
        "75": "11",
        "974": "04",
        "976": "06",
    },  # fmt: skip
    libelles_departements={
        "01": "Ain",
        "2A": "Corse-du-Sud",
        "23": "Creuse",
        "75": "Paris",
        "974": "La Réunion",
        "976": "Mayotte",
    },  # fmt: skip
)


def _lire(connecteur, nom):
    return list(connecteur.lire(FIXTURES / nom, REFERENTIEL))


def _importer(connecteur, nom):
    chemin = FIXTURES / nom
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_tranches():
    assert tranche("[0;5[") == (0, 4)
    assert tranche("[90;95[") == (90, 94)
    assert tranche("[95;99+]") == (95, None)


def test_groupe_avenir():
    assert CONNECTEURS["avenir"] == (PROJECTIONS_DEPARTEMENTALES, PROJECTIONS_FRANCE)
    assert [f.nom for f in PROJECTIONS_DEPARTEMENTALES.fichiers()] == [
        "donnees_det_Central.xlsx",
        "donnees_det_Pop_basse.xlsx",
        "donnees_det_Pop_haute.xlsx",
    ]


def test_lecture_omphale():
    lignes = _lire(OMPHALE, "donnees_det_Central.xlsx")
    assert {p.scenario for p in lignes} == {"INSEE_CENTRAL"}
    pop = [p for p in lignes if p.indicateur == "PROJ_POP"]
    assert {p.periode.year for p in pop} == {2018, *range(2020, 2071, 5)}
    # « Réunion » (INSEE) rattachée au code 974 (« La Réunion » dans le référentiel).
    assert {p.code for p in pop if p.niveau == "DEP"} == {"01", "2A", "23", "75", "974", "976"}

    def total(code, annee, sexe="T"):
        return next(
            p.valeur
            for p in pop
            if p.code == code and p.periode.year == annee and p.sexe == sexe
            and p.age_min is None
        )  # fmt: skip

    assert total("23", 2018) == total("23", 2018, "H") + total("23", 2018, "F")
    tranches_creuse = [
        p.valeur for p in pop
        if p.code == "23" and p.periode.year == 2050 and p.sexe == "T" and p.age_min is not None
    ]  # fmt: skip
    assert len(tranches_creuse) == 20 and sum(tranches_creuse) == total("23", 2050)
    # France = somme des départements ; métropole sans La Réunion ni Mayotte.
    departements = ("01", "2A", "23", "75", "974", "976")
    assert total("FR", 2070) == sum(total(c, 2070) for c in departements)
    assert total("FM", 2070) == sum(total(c, 2070) for c in ("01", "2A", "23", "75"))
    soldes = [p for p in lignes if p.indicateur == "PROJ_SOLDE_NATUREL" and p.code == "23"]
    assert soldes and all(p.periode_fin == date(p.periode.year, 12, 31) for p in soldes)
    assert max(p.periode.year for p in soldes) == 2065  # flux jusqu'en 2069-2070


def test_lecture_projections_france():
    lignes = _lire(PROJECTIONS_FRANCE, "ip2108.xlsx")
    totaux = {(p.scenario, p.periode.year): p.valeur for p in lignes if p.age_min is None}
    # Insee Première n° 2108 : 65,9 millions en 2070 (central), entre 54,6 et 78,3.
    assert totaux[("INSEE_CENTRAL", 2070)] == 65_887_000
    assert totaux[("INSEE_POP_BASSE", 2070)] == 54_639_000
    assert totaux[("INSEE_POP_HAUTE", 2070)] == 78_260_000
    seniors = next(
        p for p in lignes if p.periode.year == 2070 and (p.age_min, p.age_max) == (65, None)
    )
    assert seniors.valeur == 21_100_000 and seniors.scenario == "INSEE_CENTRAL"


def test_import_et_vues(urls_module):
    for nom in ("donnees_det_Central.xlsx", "donnees_det_Pop_haute.xlsx"):
        resultat = _importer(OMPHALE, nom)
        assert resultat.statut == "PUBLIE", resultat.message
    resultat = _importer(PROJECTIONS_FRANCE, "ip2108.xlsx")
    assert resultat.statut == "PUBLIE", resultat.message
    # Même fichier : rien à refaire.
    assert _importer(OMPHALE, "donnees_det_Central.xlsx").statut == "DEJA_IMPORTE"

    with db.connexion("lecture") as conn:
        creuse = conn.execute(
            """SELECT scenario, annee, population, part_75_plus, seniors_pour_100_actifs
               FROM api.projection_population
               WHERE niveau = 'DEP' AND code = '23' AND annee IN (2018, 2050)
               ORDER BY scenario, annee"""
        ).fetchall()
        n = conn.execute("SELECT count(*) AS n FROM api.projection").fetchone()["n"]
    assert [(c["scenario"], c["annee"]) for c in creuse] == [
        ("INSEE_CENTRAL", 2018), ("INSEE_CENTRAL", 2050),
        ("INSEE_POP_HAUTE", 2018), ("INSEE_POP_HAUTE", 2050),
    ]  # fmt: skip
    assert creuse[0]["population"] == creuse[2]["population"]  # même point de départ
    assert creuse[1]["seniors_pour_100_actifs"] > creuse[0]["seniors_pour_100_actifs"]
    assert n > 0


def test_pages_et_api(urls_module):
    client = TestClient(app)
    accueil = client.get("/")
    assert 'href="/avenir"' in accueil.text
    vue = client.get("/avenir")
    assert vue.status_code == 200
    assert "65,9 millions" in vue.text  # projections nationales 2026, scénario central
    assert "54,6 millions" in vue.text and "78,3 millions" in vue.text
    assert 'href="/avenir/DEP/23"' in vue.text
    assert 'aria-current="page"' in vue.text and "donnees-avenir" in vue.text
    fiche = client.get("/avenir/DEP/23")
    assert fiche.status_code == 200
    assert "Population en 2050" in fiche.text and "Seniors pour 100 actifs" in fiche.text
    assert 'href="/territoire/DEP/23"' in fiche.text and "Omphale 2022" in fiche.text
    # Département sans projection importée (hors des fichiers de test) : page sans graphique.
    vide = client.get("/avenir/DEP/33")
    assert vide.status_code == 200 and "pas encore importées" in vide.text
    assert client.get("/avenir/DEP/999").status_code == 404

    params = {"indicateur": "PROJ_POP", "niveau": "DEP", "code": "23", "scenario": "INSEE_CENTRAL"}
    api = client.get("/api/v1/projections", params=params)
    assert api.status_code == 200, api.text
    corps = api.json()
    annees = {v["annee"] for v in corps["valeurs"]}
    assert annees == {2018, *range(2020, 2071, 5)}
    params = {"indicateur": "POP", "niveau": "DEP", "code": "23"}
    assert client.get("/api/v1/projections", params=params).status_code == 404


def test_rejets(urls_module):
    # Couverture : le fichier réduit ne compte que 6 départements sur 101.
    resultat = _importer(PROJECTIONS_DEPARTEMENTALES, "donnees_det_Central.xlsx")
    assert resultat.statut in ("REJETE", "DEJA_IMPORTE")
    with db.connexion("import") as conn:
        conn.execute("DELETE FROM stat.projection")
        conn.execute("DELETE FROM ingest.import WHERE source_id = "
                     "(SELECT source_id FROM ref.source WHERE code = 'INSEE_OMPHALE')")  # fmt: skip
        conn.commit()
    resultat = _importer(PROJECTIONS_DEPARTEMENTALES, "donnees_det_Central.xlsx")
    assert resultat.statut == "REJETE"
    assert "6 département(s) sur 101 attendus" in resultat.message


def test_point_de_depart(urls_module):
    """Une population projetée de 2018 trop éloignée des estimations est rejetée."""
    with db.connexion("import") as conn:
        conn.execute("DELETE FROM stat.projection")
        conn.execute("DELETE FROM ingest.import WHERE source_id = "
                     "(SELECT source_id FROM ref.source WHERE code = 'INSEE_OMPHALE')")  # fmt: skip
        source = conn.execute(
            "SELECT source_id FROM ref.source WHERE code = 'INSEE_EST'"
        ).fetchone()["source_id"]
        import_id = conn.execute(
            """INSERT INTO ingest.import (source_id, url, fichier_nom, sha256, taille_octets,
                                          statut)
               VALUES (%s, 'file:///test', 'test', repeat('0', 64), 0, 'PUBLIE')
               RETURNING import_id""",
            (source,),
        ).fetchone()["import_id"]
        conn.execute(
            """INSERT INTO stat.observation (indicateur_id, territoire_id, periode,
                                             periode_type, valeur, statut, import_id)
               SELECT i.indicateur_id, t.territoire_id, '2018-01-01', '1ER_JANVIER',
                      100000, 'DEFINITIF', %s
               FROM ref.indicateur i, ref.territoire t
               WHERE i.code = 'POP' AND t.niveau = 'DEP' AND t.code = '23'""",
            (import_id,),
        )
        conn.commit()
    resultat = _importer(OMPHALE, "donnees_det_Central.xlsx")
    assert resultat.statut == "REJETE"
    assert "DEP 23 2018" in resultat.message and "estimation INSEE 100000" in resultat.message
