"""Appli 5, phase D : pages thème (carte et classement des départements) et questions
guidées de « Quel avenir pour les Français ? »."""

import dataclasses

from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import PROJECTIONS_DEPARTEMENTALES
from demographie.imports.connecteurs.climat import CLIMAT
from demographie.imports.connecteurs.gaspar import GASPAR
from demographie.imports.modele import Fichier
from demographie.web.avenir import QUESTIONS, _format

# Les fichiers Omphale de test ne gardent que six départements.
OMPHALE = dataclasses.replace(PROJECTIONS_DEPARTEMENTALES, departements_attendus=6)


def _importer(connecteur, nom):
    chemin = FIXTURES / nom
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )
    assert resultat.statut == "PUBLIE", resultat.message


def test_format():
    assert _format(12.34, "pourcentage_signe") == "+12,3 %"
    assert _format(-3, "pourcentage_signe") == "−3,0 %"
    assert _format(14.2, "pourcentage") == "14,2 %"
    assert _format(1096, "nombre") == "1 096"
    assert _format(2.345, "degres_c") == "+2,3 °C"
    assert _format(None, "nombre") == "—"


def test_pages_themes(urls_module):
    _importer(OMPHALE, "donnees_det_Central.xlsx")
    _importer(CLIMAT, "climat-cmip6-hd35-ssp585.csv")
    _importer(GASPAR, "gaspar.zip")
    client = TestClient(app)

    vue = client.get("/avenir")
    assert vue.status_code == 200 and "Questions guidées" in vue.text
    for _titre, lien in QUESTIONS:
        assert lien.replace("&", "&amp;") in vue.text
    for _titre, lien in QUESTIONS[:3] + QUESTIONS[5:]:
        assert client.get(lien).status_code == 200, lien

    population = client.get("/avenir/theme/population")
    assert population.status_code == 200
    assert "Évolution de la population depuis 2018, 2050" in population.text
    assert 'href="/avenir/DEP/23"' in population.text and "Sans donnée" in population.text
    seniors = client.get("/avenir/theme/population", params={"indicateur": "SENIORS",
                                                             "annee": 2070})  # fmt: skip
    assert seniors.status_code == 200 and "pour 100 actifs (20-64 ans), 2070" in seniors.text
    assert client.get("/avenir/theme/population", params={"annee": 2040}).status_code == 404

    # Seul SSP5-8.5 est importé ici.
    climat = client.get("/avenir/theme/climat", params={"climat": "GIEC_SSP585"})
    assert climat.status_code == 200
    assert "Jours de forte chaleur en plus, 2080-2099" in climat.text
    assert "Bouches-du-Rhône" in climat.text and "+47 jours" in climat.text
    assert client.get("/avenir/theme/climat").status_code == 404  # SSP2-4.5 absent
    assert client.get("/avenir/theme/climat", params={"climat": "RCP45"}).status_code == 422

    risques = client.get("/avenir/theme/risques")
    assert risques.status_code == 200
    assert "Communes reconnues en sécheresse en 10 ans" in risques.text
    assert "12,6 %" in risques.text  # Creuse, 2014-2023
    cumul = client.get("/avenir/theme/risques", params={"indicateur": "CATNAT_10ANS"})
    assert cumul.status_code == 200 and "2014-2023" in cumul.text
    assert client.get("/avenir/theme/eau").status_code == 404
    assert client.get("/avenir/theme/risques", params={"indicateur": "POP"}).status_code == 404

    fiche = client.get("/avenir/DEP/23")
    assert 'href="/avenir/theme/climat"' in fiche.text
