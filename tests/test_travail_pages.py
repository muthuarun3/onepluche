"""Appli travail, PR T3 : pages /travail (vue France, fiche département, carte par thème),
sans données puis avec les extraits réels des PR T1 et T2."""

import dataclasses
import re

from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import vivre
from demographie.imports.connecteurs.bdm import CHOMAGE
from demographie.imports.connecteurs.bmo import BMO
from demographie.imports.connecteurs.contrats import CONTRATS
from demographie.imports.connecteurs.dares import DEMANDEURS
from demographie.imports.connecteurs.travail import (
    CHOMAGE_ANNUEL,
    CREATIONS,
    DEFAILLANCES,
    EMPLOI_SALARIE,
    EMPLOI_TOTAL,
)
from demographie.imports.modele import Fichier
from demographie.web.travail import libelle_periode, signe

client = TestClient(app)


def _page(adresse: str, **params) -> str:
    """Texte de la page, espaces insécables remplacées par des espaces ordinaires."""
    reponse = client.get(adresse, params=params)
    assert reponse.status_code == 200, adresse
    return reponse.text.replace("\u202f", " ").replace("\u00a0", " ")


def test_signe_et_periodes():
    from datetime import date

    assert signe(3.24) == "+3,2 %"
    assert signe(-0.3, "point") == "−0,3 point"
    assert signe(-2.0, "point") == "−2,0 points"
    assert signe(1250, "nombre") == "+1 250"
    assert signe(None) == "—"
    assert libelle_periode(date(2026, 1, 1), "TRIMESTRE") == "1er trimestre 2026"
    assert libelle_periode(date(2026, 4, 1), "TRIMESTRE") == "2e trimestre 2026"
    assert libelle_periode(date(2026, 10, 1), "MOIS") == "octobre 2026"


def test_pages_sans_donnees(urls_module):
    vue = client.get("/travail")
    assert vue.status_code == 200
    assert "pas encore importés" in vue.text
    assert 'href="/travail/DEP/33"' in vue.text
    fiche = client.get("/travail/DEP/33")
    assert fiche.status_code == 200
    assert "Pas encore de chiffre du travail" in fiche.text
    theme = client.get("/travail/theme/emploi")
    assert theme.status_code == 200 and "Pas encore de donnée par département" in theme.text
    assert client.get("/travail/DEP/99").status_code == 404
    assert client.get("/travail/theme/inconnu").status_code == 404


def _importer(connecteur, chemin):
    # Extraits de quelques départements : ni couverture complète ni sommes nationales.
    reduit = dataclasses.replace(connecteur, controle_couverture=False, tolerance_sommes=1.0)
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, reduit, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )
    assert resultat.statut == "PUBLIE", (chemin.name, resultat.message)


def test_pages(urls_module):
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn,
            CHOMAGE,
            Fichier(url=(FIXTURES / "TAUX-CHOMAGE.xml").resolve().as_uri(), nom="TAUX-CHOMAGE.xml"),
            config.charger().donnees_brutes,
            chemin_local=FIXTURES / "TAUX-CHOMAGE.xml",
        )
    assert resultat.statut == "PUBLIE", resultat.message
    for jeu in (CHOMAGE_ANNUEL, EMPLOI_SALARIE, EMPLOI_TOTAL, CREATIONS, DEFAILLANCES):
        _importer(jeu, FIXTURES / jeu.nom_fichier)
    _importer(DEMANDEURS, FIXTURES / DEMANDEURS.nom_fichier)
    _importer(BMO, FIXTURES / "bmo-2026.xlsx")
    _importer(CONTRATS, FIXTURES / CONTRATS.nom_fichier)
    for jeu in (vivre.SALAIRES_CATEGORIES, vivre.SALAIRES_AGES):
        _importer(jeu, FIXTURES / jeu.nom_fichier)

    vue = _page("/travail")
    assert "pas encore importés" not in vue
    # Les quatre questions guidées, chacune vers son bloc.
    bloc = vue[vue.index('class="bloc questions-guidees"') :]
    bloc = bloc[: bloc.index("</section>")]
    ancres = re.findall(r'<li><a href="#([a-z]+)">[^<]+\?</a></li>', bloc)
    assert ancres == ["chomage", "metiers", "entreprises", "secteurs"]
    assert all(f'id="{a}"' in vue for a in ancres)
    assert "8,3 %" in vue  # chômage France, 2e trimestre 2026
    assert "/static/securite.js" in vue

    gironde = _page("/travail/DEP/33")
    assert "156 520" in gironde  # demandeurs d'emploi ABC, 3e trimestre 2026
    assert "45,8 %" in gironde  # dont inscrits depuis un an ou plus
    assert "67 045" in gironde and "47,1 %" in gironde  # projets BMO 2026
    assert "702 900" in gironde  # salariés, 2e trimestre 2026
    assert re.search(r"rang <strong>\d+</strong> sur \d+", gironde)
    assert 'href="/territoire/DEP/33"' in gironde
    assert "Les plus difficiles" in gironde
    paris = _page("/travail/DEP/75")
    assert "6,6 %" in paris  # chômage, 2e trimestre 2026 (provisoire)
    assert "2e trimestre 2026 (provisoire)" in paris
    assert "15,1 %" in gironde and "14,3 %" in gironde  # contrats courts, temps partiel
    assert "15-24 ans 50,2 %" in gironde
    assert "3 836 €" in paris  # salaire net moyen 2024
    assert re.search(r"de moins</strong>", paris)
    assert "Moins de 25 ans" in paris
    salaires = _page("/travail/theme/salaires")
    assert 'value="SALAIRE_NET_MOYEN" selected' in salaires and "3 836 €" in salaires
    assert 'value="PART_CONTRATS_COURTS" selected' in _page("/travail/theme/comment")
    mayotte = client.get("/travail/DEP/976")
    assert mayotte.status_code == 200 and "Mayotte n'est pas publiée" in mayotte.text

    carte = _page("/travail/theme/chercher-creer")
    assert 'value="TAUX_CHOMAGE" selected' in carte
    assert '<a href="/travail/DEP/75" aria-label="Paris' in carte
    metiers = _page(
        "/travail/theme/chercher-creer", indicateur="PART_RECRUTEMENTS_DIFFICILES", famille="V"
    )
    assert "Fonctions liées à la vente" in metiers
    assert "46,8 %" in metiers  # Gironde, famille vente, tourisme et services
    refus = client.get("/travail/theme/emploi", params={"indicateur": "TAUX_CHOMAGE"})
    assert refus.status_code == 404
    refus = client.get("/travail/theme/emploi", params={"famille": "V"})
    assert refus.status_code == 404

    accueil = client.get("/").text
    assert 'href="/travail"' in accueil and "Comment travaillent les Français ?" in accueil
