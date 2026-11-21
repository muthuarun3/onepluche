"""Appli 2, phase D : pages /besoins (choix du département, fiche département)."""

import dataclasses

from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import EstimationsDepartements, besoins, energie, soins
from demographie.imports.modele import Fichier, Referentiel
from demographie.web.besoins import valeur_unite

client = TestClient(app)


def test_valeur_unite():
    assert valeur_unite(12.44, "euros_m2") == "12,4 €/m²"
    assert valeur_unite(29.5, "pourcentage") == "29,5 %"
    assert valeur_unite(5416826, "logements") == "5 416 826"
    assert valeur_unite(None, "euros") == "—"


def test_budget_des_menages():
    lignes = list(
        besoins.DEPENSES_MENAGES.lire(
            FIXTURES / besoins.DEPENSES_MENAGES.nom_fichier, Referentiel(identifiants={})
        )
    )
    an_2024 = [x for x in lignes if x.periode.year == 2024]
    total = next(x.valeur for x in an_2024 if x.modalite is None)
    assert len(an_2024) == 14  # total + 13 postes
    assert abs(sum(x.valeur for x in an_2024 if x.modalite) - total) < 1
    assert {x.statut for x in an_2024} == {"PROVISOIRE"}
    assert {x.statut for x in lignes if x.periode.year == 2022} == {"DEFINITIF"}
    pre = list(
        besoins.DEPENSE_PRE_ENGAGEE.lire(
            FIXTURES / besoins.DEPENSE_PRE_ENGAGEE.nom_fichier, Referentiel(identifiants={})
        )
    )
    assert str(next(x.valeur for x in pre if x.periode.year == 2024)) == "30.077"


def _importer(connecteur, nom):
    chemin = FIXTURES / nom
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_pages(urls_module):
    apl = dataclasses.replace(soins.APL_MEDECINS, communes_min=100, controle_couverture=False)
    filosofi = [
        dataclasses.replace(j, controle_couverture=False, tolerance_sommes=1.0)
        for j in (besoins.NIVEAU_DE_VIE, besoins.PAUVRETE)
    ]
    etapes = [
        (EstimationsDepartements(), "estim-pop-dep-sexe-aq-1975-2026.xlsx"),
        (apl, apl.nom_fichier),
        (soins.ALD_SANS_MEDECIN_TRAITANT, soins.ALD_SANS_MEDECIN_TRAITANT.nom_fichier),
        *((j, j.nom_fichier) for j in filosofi),
        (besoins.DEPENSES_MENAGES, besoins.DEPENSES_MENAGES.nom_fichier),
        (besoins.DEPENSE_PRE_ENGAGEE, besoins.DEPENSE_PRE_ENGAGEE.nom_fichier),
        (energie.PRIX, energie.PRIX.nom_fichier),
    ]
    for connecteur, nom in etapes:
        resultat = _importer(connecteur, nom)
        assert resultat.statut == "PUBLIE", resultat.message

    accueil = client.get("/besoins")
    assert accueil.status_code == 200
    vue = accueil.text
    assert 'href="/besoins/DEP/23"' in vue
    # Budget 2025 (provisoire) : logement en tête, dépenses pré-engagées.
    assert "Le budget des ménages" in vue and "milliards d'euros" in vue
    assert vue.index("Logement, eau, gaz") < vue.index("Alimentation et boissons")
    assert "30,3\u00a0%" in vue
    # Prix : l'extrait commence en 2024, première année complète.
    assert "Les prix depuis 2024" in vue and "Entre 2024 et 2025" in vue
    assert "Accès aux soins · Accès aux médecins généralistes" in vue

    page = client.get("/besoins/DEP/23")
    assert page.status_code == 200
    html = page.text
    assert "<h1>Creuse" in html
    assert "2,40 consultations" in html  # accès aux généralistes, 2024
    assert "9,6 %" in html and "France : 4,3 %" in html  # ALD sans médecin traitant
    # Loyer non importé ici : affiché comme absent, jamais comme zéro.
    assert "Pas de donnée pour ce département" in html
    assert "Accès aux soins" in html and "Manque" in html
    # Encadré 18-39 ans (Filosofi), France métropolitaine en comparaison.
    assert "Les 18-39 ans" in html and "18-29 ans" in html and "(métropole)" in html
    assert 'href="/territoire/DEP/23"' in html
    # Indice des prix : national, absent de la fiche.
    assert "Indice des prix" not in html

    assert client.get("/besoins/DEP/99").status_code == 404
    assert client.get("/besoins/DEP/ABC").status_code == 422
