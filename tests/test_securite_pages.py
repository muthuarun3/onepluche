"""Appli sécurité, PR S3 : pages /securite (vue France, fiche département, carte par
famille), sans données puis avec les extraits réels des fichiers."""

import dataclasses
import re

from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import (
    EstimationsDepartements,
    delinquance,
    ressenti,
    routes,
)
from demographie.imports.modele import Fichier
from demographie.web.securite import chiffre, phrase_evolution

client = TestClient(app)


def test_chiffre():
    assert chiffre(211596, "nombre") == "211 596"
    assert chiffre(6.123, "pour_mille") == "6,12 ‰"
    assert chiffre(0.0143, "pour_mille") == "0,014 ‰"
    assert chiffre(43.4, "par_million") == "43 par million"
    assert chiffre(22, "pourcentage") == "22 %"
    assert chiffre(18.4, "pourcentage") == "18,4 %"
    assert chiffre(None, "nombre") == "—"


def test_phrase_evolution():
    assert phrase_evolution(-15.2, 2016) == "15 % de moins qu'en 2016"
    assert phrase_evolution(120.4, 2016) == "120 % de plus qu'en 2016"
    assert phrase_evolution(0.2, 2016) == "autant qu'en 2016"
    assert phrase_evolution(None, 2016) == ""


def test_pages_sans_donnees(urls_module):
    vue = client.get("/securite")
    assert vue.status_code == 200
    assert "pas encore importés" in vue.text
    assert 'href="/securite/DEP/23"' in vue.text
    fiche = client.get("/securite/DEP/23")
    assert fiche.status_code == 200
    assert "Pas encore de chiffre" in fiche.text
    assert client.get("/securite/famille/vols").status_code == 200
    assert client.get("/securite/DEP/99").status_code == 404
    assert client.get("/securite/famille/inconnue").status_code == 404
    # Le ressenti n'a pas de carte : publié pour la France seulement.
    assert client.get("/securite/famille/ressenti").status_code == 404


def _importer(connecteur, chemin):
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )
    assert resultat.statut == "PUBLIE", resultat.message


def test_pages(urls_module):
    _importer(EstimationsDepartements(), FIXTURES / "estim-pop-dep-sexe-aq-1975-2026.xlsx")
    _importer(
        dataclasses.replace(delinquance.DELINQUANCE, controle_couverture=False),
        FIXTURES / "delinquance-departements.csv",
    )
    accidents = dataclasses.replace(routes.ACCIDENTS, controle_couverture=False)
    for annee in (2016, 2025):
        _importer(accidents, FIXTURES / f"accidents-{annee}.zip")
    _importer(ressenti.CVS, FIXTURES / ressenti.CVS.nom_fichier)
    for fiche in ("8242369", "8612552"):
        _importer(ressenti.VRS, FIXTURES / f"insee-victimation-{fiche}.xlsx")

    vue = client.get("/securite").text
    # Une carte par famille, les faits avant le ressenti.
    positions = [vue.index(f'id="{f}"') for f in ("personnes", "vols", "biens", "stupefiants")]
    positions += [vue.index('id="routes"'), vue.index('id="ressenti"')]
    assert positions == sorted(positions)
    assert "cambriolages de logement enregistrés en 2025" in vue
    assert "personnes tuées sur les routes en 2025" in vue
    assert 'id="evolution"' in vue and 'id="violences-sexuelles"' in vue
    # Les six questions guidées, chacune avec son lien.
    bloc = vue[vue.index('class="bloc questions-guidees"') :]
    bloc = bloc[: bloc.index("</section>")]
    questions = re.findall(r'<li><a href="([^"]+)">[^<]+\?</a></li>', bloc)
    assert len(questions) == 6
    assert "/securite/famille/vols?indicateur=TAUX_CAMBRIOLAGES" in questions
    # Ressenti : la courbe est coupée entre les deux enquêtes (null en 2020 et 2021).
    courbes = re.findall(r"data-courbe='([^']+)'", vue)
    assert any("null" in c and "2020" in c for c in courbes)
    assert "/static/securite.js" in vue

    paris = client.get("/securite/DEP/75").text
    assert "Paris accueille" in paris
    assert "Cambriolages de logement" in paris
    assert re.search(r"rang <strong>\d+</strong> sur \d+", paris)
    assert 'href="/territoire/DEP/75"' in paris
    creuse = client.get("/securite/DEP/23").text
    assert "Paris accueille" not in creuse and "très touristique" not in creuse
    assert "Tués sur la route" in creuse
    assert "très touristique" in client.get("/securite/DEP/2A").text

    vols = client.get("/securite/famille/vols")
    assert vols.status_code == 200
    # Par défaut, le taux de cambriolages ; la carte mène aux fiches sécurité.
    assert 'value="TAUX_CAMBRIOLAGES" selected' in vols.text
    assert '<a href="/securite/DEP/75" aria-label="Paris' in vols.text
    assert "‰" in vols.text
    routes_page = client.get("/securite/famille/routes")
    assert 'value="TAUX_TUES_ROUTE" selected' in routes_page.text
    assert "par million" in routes_page.text
    # Un indicateur d'une autre famille est refusé.
    reponse = client.get("/securite/famille/vols", params={"indicateur": "TAUX_HOMICIDES"})
    assert reponse.status_code == 404

    accueil = client.get("/").text
    assert 'href="/securite"' in accueil
    assert "Les Français sont-ils en sécurité ?" in accueil
