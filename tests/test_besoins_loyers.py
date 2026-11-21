"""Appli 2, phase B : poids communaux du recensement et Carte des loyers (extraits réels)."""

import dataclasses
import shutil
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline, telechargement
from demographie.imports.connecteurs import communes, loyers
from demographie.imports.connecteurs.besoins import POIDS_RP_LOUEES
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
NOMS = sorted(f"carte-loyers-2025-{n}" for n in loyers.FICHIERS)
# Extraits réduits : 3 départements, et le millésime 2023 seulement des poids.
POIDS_TEST = dataclasses.replace(POIDS_RP_LOUEES, communes_min=300)
LOYERS_TEST = dataclasses.replace(loyers.CARTE_DES_LOYERS, controle_couverture=False)


def _poids() -> dict[str, Decimal]:
    return {
        p.commune: p.poids
        for p in POIDS_RP_LOUEES.lire(FIXTURES / POIDS_RP_LOUEES.nom_fichier, Referentiel({}))
    }


def _referentiel() -> Referentiel:
    return Referentiel(
        identifiants={},
        region_du_departement={"23": "75", "75": "11", "971": "01"},
        poids_communes={("RP_LOUEES", 2023): _poids()},
    )


def _lire(nom):
    lignes = loyers.CARTE_DES_LOYERS.lire(FIXTURES / nom, _referentiel())
    return {(x.niveau, x.code): x for x in lignes}


def test_poids_communaux():
    poids = _poids()
    assert len(poids) == 255 + 20 + 1 + 32  # Creuse, arrondissements et Paris, Guadeloupe
    assert round(poids["75112"]) == 47036  # résidences principales louées, Paris 12e
    assert round(poids["23096"]) == 3625  # Guéret


def test_moyenne_ponderee_par_groupe():
    poids = {"23096": Decimal(3), "75112": Decimal(1)}
    valeurs = [("23096", Decimal(8)), ("75112", Decimal(32))]
    france = communes.moyenne_ponderee(valeurs, poids, lambda _c: "FR")
    assert france["FR"].valeur == 14
    seule = communes.moyenne_ponderee(valeurs, poids, lambda c: None if c[:2] == "75" else "X")
    assert seule["X"].valeur == 8


def test_loyers_appartements():
    lignes = _lire("carte-loyers-2025-pred-app-mef-dhup.csv")
    assert lignes[("DEP", "23")].valeur == Decimal("8.46")
    assert lignes[("DEP", "75")].valeur == Decimal("31.37")
    assert lignes[("DEP", "23")].modalite is None
    assert lignes[("DEP", "23")].indicateur == "LOYER_APPARTEMENT_M2"
    # La France métropolitaine laisse la Guadeloupe (loyers plus bas que Paris) de côté.
    assert lignes[("FRANCE", "FM")].valeur > lignes[("FRANCE", "FR")].valeur
    assert ("REG", "11") in lignes


def test_loyers_par_taille_et_maisons():
    petits = _lire("carte-loyers-2025-pred-app12-mef-dhup.csv")[("DEP", "75")]
    assert petits.indicateur == "LOYER_APPARTEMENT_M2"
    assert petits.modalite == ("taille_appartement", "T1_T2")
    maison = _lire("carte-loyers-2025-pred-mai-mef-dhup.csv")[("DEP", "23")]
    assert maison.indicateur == "LOYER_MAISON_M2" and maison.valeur == Decimal("7.75")


def test_loyers_sans_poids_refuses():
    with pytest.raises(FichierIllisible, match="Poids communaux absents"):
        list(loyers.CARTE_DES_LOYERS.lire(FIXTURES / NOMS[0], Referentiel({})))


def test_decouverte_de_la_derniere_edition(monkeypatch):
    def jeu(annee):
        base = f"https://static.data.gouv.fr/resources/x-{annee}"
        return {
            "slug": f"carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-{annee}",
            "resources": [{"url": f"{base}/{n}"} for n in [*loyers.FICHIERS, "note.pdf"]],
        }

    reponse = {"data": [jeu(2024), jeu(2025), {"slug": "autre-jeu", "resources": []}]}
    monkeypatch.setattr(telechargement, "lire_json", lambda _url: reponse)
    fichiers = loyers.CARTE_DES_LOYERS.fichiers()
    assert [f.nom for f in fichiers] == NOMS
    assert {f.millesime for f in fichiers} == {"2025"}
    assert all(loyers.CARTE_DES_LOYERS.accepte(f.nom) for f in fichiers)


def _importer(connecteur, chemin):
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_loyers_avant_les_poids_rejetes(urls_module):
    resultat = _importer(LOYERS_TEST, FIXTURES / NOMS[0])
    assert resultat.statut == "REJETE"
    assert "Poids communaux absents" in resultat.message


def test_poids_incomplets_rejetes(urls_module, tmp_path):
    copie = tmp_path / POIDS_RP_LOUEES.nom_fichier
    shutil.copyfile(FIXTURES / POIDS_RP_LOUEES.nom_fichier, copie)
    resultat = _importer(POIDS_RP_LOUEES, copie)
    assert resultat.statut == "REJETE"
    assert "RP_LOUEES 2023 : 308 communes (minimum 30000)" in resultat.message


def test_import_et_api(urls_module):
    resultat = _importer(POIDS_TEST, FIXTURES / POIDS_RP_LOUEES.nom_fichier)
    assert resultat.statut == "PUBLIE", resultat.message
    assert "308 poids communaux (RP_LOUEES 2023)" in resultat.message
    with db.connexion("import") as conn:
        assert conn.execute("SELECT count(*) AS n FROM ingest.poids_commune").fetchone()["n"] == 308
    for nom in NOMS:
        resultat = _importer(LOYERS_TEST, FIXTURES / nom)
        assert resultat.statut == "PUBLIE", resultat.message
    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "LOYER_APPARTEMENT_M2", "niveau": "DEP", "code": "75"},
    ).json()
    assert serie["valeurs"] == [
        {
            "annee": 2025,
            "periode": "2025-01-01",
            "periode_type": "ANNEE",
            "valeur": 31.37,
            "provisoire": False,
        }  # fmt: skip
    ]
    assert serie["indicateur"]["source_code"] == "ANIL_LOYERS"
    assert serie["indicateur"]["angle"] == "COUT"
