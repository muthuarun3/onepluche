"""Appli 2, phase C : énergie (Agence ORE, DPE de l'ADEME, IPC de l'INSEE), extraits réels."""

import dataclasses
import json
from datetime import date

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import energie
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
# Deux départements « attendus » : la France est leur somme.
REFERENTIEL = Referentiel(
    identifiants={("DEP", "23"): 1, ("DEP", "75"): 2},
    region_du_departement={"23": "75", "75": "11"},
)


def _ore(connecteur, annee=2024):
    return {
        (x.indicateur, x.niveau, x.code): x.valeur
        for x in connecteur.lire(FIXTURES / connecteur.nom_fichier, REFERENTIEL)
        if x.periode == date(annee, 1, 1)
    }


def test_electricite_tous_gestionnaires():
    valeurs = _ore(energie.ELECTRICITE)
    assert valeurs[("CONSO_ELEC_RESID", "DEP", "23")] == 303918
    assert valeurs[("POINTS_ELEC_RESID", "DEP", "75")] > 1_300_000
    france = valeurs[("CONSO_ELEC_RESID", "FRANCE", "FR")]
    assert (
        france
        == valeurs[("CONSO_ELEC_RESID", "DEP", "23")] + valeurs[("CONSO_ELEC_RESID", "DEP", "75")]
    )


def test_region_incomplete_non_publiee(tmp_path):
    # Paris seul : l'Île-de-France est publiée ; sans la Creuse, ni sa région ni la France.
    contenu = json.loads((FIXTURES / energie.ELECTRICITE.nom_fichier).read_text())
    contenu["lignes"] = [x for x in contenu["lignes"] if x["code_departement"] == "75"]
    chemin = tmp_path / energie.ELECTRICITE.nom_fichier
    chemin.write_text(json.dumps(contenu))
    territoires = {(x.niveau, x.code) for x in energie.ELECTRICITE.lire(chemin, REFERENTIEL)}
    assert territoires == {("DEP", "75"), ("REG", "11")}


def test_gaz_secret_ignore():
    valeurs = _ore(energie.GAZ)
    assert valeurs[("CONSO_GAZ_RESID", "DEP", "23")] > 0
    assert ("POINTS_GAZ_RESID", "FRANCE", "FM") in valeurs


def test_ore_ligne_inattendue(tmp_path):
    chemin = tmp_path / energie.GAZ.nom_fichier
    chemin.write_text(json.dumps({"lignes": [{"filiere": "Electricité"}]}))
    with pytest.raises(FichierIllisible, match="Ligne inattendue"):
        list(energie.GAZ.lire(chemin, REFERENTIEL))


def test_dpe_hors_referentiel_refuse():
    # Avec deux départements seulement, presque tous les DPE sont « inconnus ».
    with pytest.raises(FichierIllisible, match="hors référentiel"):
        list(energie.DIAGNOSTICS.lire(FIXTURES / energie.DIAGNOSTICS.nom_fichier, REFERENTIEL))


def test_ipc():
    lignes = list(energie.PRIX.lire(FIXTURES / energie.PRIX.nom_fichier, REFERENTIEL))
    octobre = {x.modalite: x.valeur for x in lignes if x.periode == date(2026, 10, 1)}
    assert str(octobre[None]) == "103.46"
    assert str(octobre[("poste_ipc", "GAZ")]) == "125.13"
    assert len(octobre) == 9  # ensemble + 8 postes
    assert {x.periode_type for x in lignes} == {"MOIS"}


def test_ipc_serie_absente(tmp_path):
    xml = (FIXTURES / energie.PRIX.nom_fichier).read_text(encoding="utf-8")
    debut = xml.index('<Series IDBANK="011816281"')
    fin = xml.index("</Series>", debut) + len("</Series>")
    chemin = tmp_path / energie.PRIX.nom_fichier
    chemin.write_text(xml[:debut] + xml[fin:], encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Séries absentes : 011816281"):
        list(energie.PRIX.lire(chemin, REFERENTIEL))


def _importer(connecteur):
    chemin = FIXTURES / connecteur.nom_fichier
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_api(urls_module):
    # Agence ORE : extraits de deux départements, la couverture ne peut pas être complète.
    ore = [
        dataclasses.replace(c, controle_couverture=False)
        for c in (energie.ELECTRICITE, energie.GAZ)
    ]
    for connecteur in (*ore, energie.DIAGNOSTICS, energie.PRIX):
        resultat = _importer(connecteur)
        assert resultat.statut == "PUBLIE", resultat.message

    def valeur(indicateur, annee, niveau="DEP", code="23"):
        serie = client.get(
            "/api/v1/series",
            params={
                "indicateur": indicateur,
                "niveau": niveau,
                "code": code,
                "debut": annee,
                "fin": annee,
            },  # fmt: skip
        ).json()
        return serie["valeurs"][-1]["valeur"]

    assert valeur("CONSO_MOY_ELEC_LOGEMENT", 2024) == 3.84
    assert valeur("PART_DPE_FG", 2024) == 29.5
    assert valeur("PART_DPE_FG", 2024, "DEP", "75") == 13.3
    assert valeur("DPE_ETABLIS", 2024, "FRANCE", "FR") > 3_000_000
    assert valeur("IPC", 2026, "FRANCE", "FR") == 103.46
