"""Appli 3, phase C : pages /vivre (vue France, fiche département, carte par thème) et
questions guidées, sur les extraits réels des connecteurs de la rubrique."""

import dataclasses
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import (
    EACR,
    NIVEAU_DE_VIE,
    PAUVRETE,
    EstimationsDepartements,
    EstimationsRegions,
    caf,
    vivre,
)
from demographie.imports.connecteurs.surendettement import Surendettement
from demographie.imports.modele import Fichier

client = TestClient(app)

NOUVELLE_AQUITAINE = {"16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"}


class _SurendettementNouvelleAquitaine(Surendettement):
    """L'extrait Banque de France ne couvre qu'une région."""

    controle_couverture = False

    def lire(self, chemin, referentiel):
        libelles = {
            k: v for k, v in referentiel.libelles_departements.items() if k in NOUVELLE_AQUITAINE
        }
        return super().lire(
            chemin, dataclasses.replace(referentiel, libelles_departements=libelles)
        )


def _etapes():
    sans_couverture = (
        vivre.REVENUS_FILOSOFI,
        vivre.SALAIRES_CATEGORIES,
        vivre.SALAIRES_AGES,
        *vivre.SERIES_NATIONALES,
        caf.RSA,
        caf.AIDES_LOGEMENT,
        NIVEAU_DE_VIE,
        PAUVRETE,
    )
    yield EstimationsDepartements(), "estim-pop-dep-sexe-aq-1975-2026.xlsx"
    yield EstimationsRegions(), "estim-pop-nreg-sexe-aq-1975-2026.xlsx"
    for jeu in sans_couverture:
        yield dataclasses.replace(jeu, controle_couverture=False), jeu.nom_fichier
    yield EACR, "62_eacr_diffusee_part_1_version_du_26_mai_2026.xlsx"
    yield _SurendettementNouvelleAquitaine(), "SUREN-2025.zip"


def importer_tout() -> None:
    brut = config.charger().donnees_brutes
    with db.connexion("import") as conn:
        for connecteur, nom in _etapes():
            chemin = FIXTURES / nom
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(conn, connecteur, fichier, brut, chemin_local=chemin)
            assert resultat.statut == "PUBLIE", (nom, resultat.message)


@pytest.fixture
def donnees(urls_module):
    if not getattr(donnees, "faites", False):
        importer_tout()
        donnees.faites = True
    return urls_module


def test_formats():
    from demographie.web.vivre import ecart_signe, montant

    assert montant(23210, "euros") == "23 210 €"
    assert montant(Decimal("0.297"), "ratio") == "0,297"
    assert montant(Decimal("3.46"), "ratio") == "3,5"
    assert montant(-0.688, "evolution") == "−0,7 %"
    assert montant(1876862.7, "millions_euros") == "1 877 milliards €"
    assert montant(None, "euros") == "—"
    assert ecart_signe(-2710, "euros") == "−2 710 €"
    assert ecart_signe(2.5, "pourcentage") == "+2,5 points"


def test_vue_france(donnees):
    page = client.get("/vivre")
    assert page.status_code == 200
    texte = page.text
    # Les quatre chiffres en tête (étape 8 du dossier).
    for libelle in ("Niveau de vie médian", "Pouvoir d&#39;achat sur un an", "Taux d&#39;épargne",
                    "Rapport D9/D1"):  # fmt: skip
        assert libelle in texte
    assert "17,9 %" in texte  # taux d'épargne 2025, provisoire
    # Les six questions guidées, chacune avec son bloc.
    for ancre in ("revenus", "salaires", "pouvoir-achat", "inegalites", "parts-revenu", "aides"):
        assert f'href="#{ancre}"' in texte and f'id="{ancre}"' in texte
    assert "Calcul On épluche" in texte
    assert 'href="/vivre/DEP/23"' in texte  # choix du département


def test_pouvoir_achat_depuis(donnees):
    # L'extrait n'a pas toutes les années : on ne cumule que la suite sans trou (2019-2025).
    texte = client.get("/vivre", params={"depuis": 2020}).text
    assert "Entre 2020 et 2025" in texte
    assert client.get("/vivre", params={"depuis": 1500}).status_code == 422


def test_fiche_creuse(donnees):
    texte = client.get("/vivre/DEP/23").text
    assert "23 210 €" in texte  # niveau de vie médian (critère du dossier)
    assert "37 240 €" in texte and "12 380 €" in texte  # D9, D1
    assert "40,2 %" in texte  # part des pensions dans le revenu
    assert "Rang <strong>" in texte
    # RSA et aides au logement pour 1 000 habitants, surendettement de l'année.
    assert "19,4" in texte and "pour 1 000 habitants" in texte
    assert "319" in texte
    employes = client.get("/vivre/DEP/23", params={"categorie": "EMPLOYES"}).text
    assert "« Employés »" in employes
    assert client.get("/vivre/DEP/999").status_code == 404


def test_fiche_sans_donnees(donnees):
    # La Corse-du-Sud n'est dans aucun extrait : la fiche le dit, sans erreur.
    texte = client.get("/vivre/DEP/2A").text
    assert "Corse-du-Sud" in texte
    assert "Pas encore de chiffre sur les revenus pour ce département." in texte


def test_carte_par_theme(donnees):
    page = client.get(
        "/vivre/theme/aides-logement", params={"indicateur": "FOYERS_RSA_POUR_1000", "dep": "23"}
    )
    assert page.status_code == 200
    assert "rang <strong>9</strong> sur 12" in page.text
    assert 'class="choisi"' in page.text
    surendettement = client.get("/vivre/theme/surendettement").text
    assert "Le plus élevé · Creuse" in surendettement
    assert client.get("/vivre/theme/inconnu").status_code == 404
    assert client.get("/vivre/theme/revenus", params={"indicateur": "POP"}).status_code == 404


def test_accueil_et_barre_laterale(urls_db):
    accueil = client.get("/").text
    assert 'href="/vivre"' in accueil and "Comment vivent les Français ?" in accueil
