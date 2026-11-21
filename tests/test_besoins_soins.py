"""Appli 2, phase C : accès aux soins (APL de la DREES, ALD sans médecin traitant de
l'Assurance maladie, équipements de la BPE), extraits réels."""

import dataclasses
from datetime import date

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import EstimationsDepartements, soins
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel(
    identifiants={("DEP", "23"): 1, ("DEP", "75"): 2},
    region_du_departement={"23": "75", "75": "11"},
)
# L'extrait ne garde que les communes de la Creuse et de Paris.
APL_EXTRAIT = dataclasses.replace(soins.APL_MEDECINS, communes_min=100, controle_couverture=False)


def _apl():
    return {
        (x.indicateur, x.niveau, x.code, x.periode.year): x.valeur
        for x in APL_EXTRAIT.lire(FIXTURES / APL_EXTRAIT.nom_fichier, REFERENTIEL)
    }


def test_apl_identique_a_la_drees():
    # Classeur complet : Paris 4,57, Creuse 2,40, France hors Mayotte 3,26 (publié : 3,26).
    valeurs = _apl()
    assert str(valeurs[("APL_MG", "DEP", "75", 2024)]) == "4.57"
    assert str(valeurs[("APL_MG", "DEP", "23", 2024)]) == "2.40"
    assert {a for (_i, _n, _c, a) in valeurs} == {2022, 2023, 2024}
    assert ("APL_MG", "REG", "75", 2024) in valeurs
    assert ("APL_MG", "FRANCE", "FM", 2024) in valeurs


def test_part_des_habitants_mal_desservis():
    valeurs = _apl()
    assert str(valeurs[("PART_POP_APL_MG_FAIBLE", "DEP", "23", 2024)]) == "53.6"
    assert valeurs[("PART_POP_APL_MG_FAIBLE", "DEP", "75", 2024)] == 0


def test_apl_trop_peu_de_communes():
    with pytest.raises(FichierIllisible, match="communes seulement"):
        list(soins.APL_MEDECINS.lire(FIXTURES / APL_EXTRAIT.nom_fichier, REFERENTIEL))


def test_apl_colonne_absente(tmp_path):
    classeur = load_workbook(FIXTURES / APL_EXTRAIT.nom_fichier)
    feuille = classeur["APL 2024"]
    for rang in feuille.iter_rows():
        if rang[0].value == "Code commune INSEE":
            rang[3].value = "APL"
    chemin = tmp_path / APL_EXTRAIT.nom_fichier
    classeur.save(chemin)
    with pytest.raises(FichierIllisible, match="APL 2024 : colonne"):
        list(APL_EXTRAIT.lire(chemin, REFERENTIEL))


def test_ald_sans_medecin_traitant():
    lignes = list(
        soins.ALD_SANS_MEDECIN_TRAITANT.lire(
            FIXTURES / soins.ALD_SANS_MEDECIN_TRAITANT.nom_fichier, REFERENTIEL
        )
    )
    valeurs = {(x.niveau, x.code, x.periode): x.valeur for x in lignes}
    assert str(valeurs[("DEP", "23", date(2025, 1, 1))]) == "9.6"
    assert str(valeurs[("FRANCE", "FR", date(2025, 1, 1))]) == "4.3"
    assert str(valeurs[("REG", "75", date(2025, 1, 1))]) == "3.6"
    # « département inconnu » laissé de côté.
    assert not any(x.code == "inconnu" for x in lignes)


def test_ald_taux_hors_bornes(tmp_path):
    chemin = tmp_path / soins.ALD_SANS_MEDECIN_TRAITANT.nom_fichier
    chemin.write_text(
        "annee;region;departement;taux_patients_ald_sans_mt\n2025;75;23;9.6\n", encoding="utf-8"
    )
    with pytest.raises(FichierIllisible, match="hors de"):
        list(soins.ALD_SANS_MEDECIN_TRAITANT.lire(chemin, REFERENTIEL))


def test_bpe_medecins():
    jeu = soins.MEDECINS_GENERALISTES
    valeurs = {
        (x.niveau, x.code): x.valeur for x in jeu.lire(FIXTURES / jeu.nom_fichier, REFERENTIEL)
    }
    assert valeurs[("DEP", "23")] == 80
    assert valeurs[("FRANCE", "FR")] == 61263
    assert ("REG", "11") in valeurs


def _importer(connecteur, nom=None):
    chemin = FIXTURES / (nom or connecteur.nom_fichier)
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_api(urls_module):
    # La population (estimations) d'abord : les densités pour 10 000 habitants s'en servent.
    resultat = _importer(EstimationsDepartements(), "estim-pop-dep-sexe-aq-1975-2026.xlsx")
    assert resultat.statut == "PUBLIE", resultat.message
    connecteurs = (
        APL_EXTRAIT,
        soins.ALD_SANS_MEDECIN_TRAITANT,
        soins.MEDECINS_GENERALISTES,
        soins.PHARMACIES,
        soins.URGENCES,
        soins.MAISONS_DE_SANTE,
    )
    for connecteur in connecteurs:
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

    assert valeur("APL_MG", 2024) == 2.4
    assert valeur("ALD_SANS_MT", 2025) == 9.6
    assert valeur("LIEUX_MG", 2025) == 80
    # 80 médecins et 54 pharmacies pour environ 114 000 habitants au 1er janvier 2025.
    assert 6 < valeur("MG_10000", 2025) < 8
    assert 4 < valeur("PHARMACIES_10000", 2025) < 5
    assert valeur("PHARMACIES_10000", 2025, "FRANCE", "FR") > 2
