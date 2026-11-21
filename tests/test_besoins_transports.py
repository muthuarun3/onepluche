"""Appli 2 : courses, carburant et transports (prix des carburants par station, trajets
domicile-travail et voitures du recensement, comptes nationaux), extraits réels."""

import dataclasses
import json
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import besoins, energie, transports
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={"23": "75", "75": "11", "2A": "94", "2B": "94"},
)


def _referentiel_complet() -> Referentiel:
    """Tous les départements et régions du relevé (les codes de région sont répartis
    sur les départements : seul compte qu'ils soient connus)."""
    contenu = json.loads((FIXTURES / transports.PRIX_GAZOLE.nom_fichier).read_text())
    deps = sorted(c for c in contenu["moyennes"]["DEP"] if c)
    regions = sorted(c for c in contenu["moyennes"]["REG"] if c)
    return Referentiel(
        identifiants={},
        region_du_departement={d: regions[i % len(regions)] for i, d in enumerate(deps)},
    )


def test_prix_des_carburants():
    lignes = {
        (x.niveau, x.code): x
        for x in transports.PRIX_GAZOLE.lire(
            FIXTURES / transports.PRIX_GAZOLE.nom_fichier, _referentiel_complet()
        )
    }
    # Relevé du 21/11/2026 : gazole à 2,124 € en métropole, 2,165 € dans la Creuse.
    assert str(lignes[("FRANCE", "FM")].valeur) == "2.124"
    assert str(lignes[("DEP", "23")].valeur) == "2.165"
    assert lignes[("DEP", "23")].periode.isoformat() == "2026-11-01"
    assert lignes[("DEP", "23")].periode_type == "MOIS"
    assert len([k for k in lignes if k[0] == "DEP"]) == 96
    # Pas de SP95-E10 en Corse ; un département sans assez de stations n'est pas publié.
    e10 = {
        (x.niveau, x.code)
        for x in transports.PRIX_SP95_E10.lire(
            FIXTURES / transports.PRIX_SP95_E10.nom_fichier, _referentiel_complet()
        )
    }
    assert ("DEP", "2A") not in e10 and ("DEP", "23") in e10


def test_territoire_inconnu():
    with pytest.raises(FichierIllisible, match="Territoire inconnu"):
        list(
            transports.PRIX_GAZOLE.lire(FIXTURES / transports.PRIX_GAZOLE.nom_fichier, REFERENTIEL)
        )


def test_carburant_inattendu(tmp_path):
    chemin = tmp_path / "prix-carburants-e10.json"
    contenu = json.loads((FIXTURES / "prix-carburants-gazole.json").read_text())
    chemin.write_text(json.dumps(contenu))
    with pytest.raises(FichierIllisible, match="Relevé inattendu"):
        list(transports.PRIX_SP95_E10.lire(chemin, REFERENTIEL))


def test_prix_hors_bornes(tmp_path):
    chemin = tmp_path / "prix-carburants-gazole.json"
    contenu = {"releve": "2026-11-21", "carburant": "gazole",
               "moyennes": {"DEP": {"23": [12.5, 30]}, "REG": {}, "FRANCE": {}}}  # fmt: skip
    chemin.write_text(json.dumps(contenu))
    with pytest.raises(FichierIllisible, match="hors bornes"):
        list(transports.PRIX_GAZOLE.lire(chemin, REFERENTIEL))


def test_trajets_et_voitures():
    trajets = {
        (x.code, x.periode.year, x.modalite): x.valeur
        for x in transports.TRAJETS_TRAVAIL.lire(
            FIXTURES / transports.TRAJETS_TRAVAIL.nom_fichier, REFERENTIEL
        )
        if x.niveau == "DEP"
    }
    total = trajets[("23", 2023, None)]
    voiture = trajets[("23", 2023, ("mode_transport", "VOITURE"))]
    assert float(round(100 * voiture / total, 1)) == pytest.approx(81.6, abs=0.1)
    # « 3T4 » (deux-roues) non repris : les modes font le total.
    modes = sum(v for (c, a, m), v in trajets.items() if c == "23" and a == 2023 and m)
    assert abs(modes - total) < 1
    voitures = {
        (x.code, x.periode.year, x.modalite): x.valeur
        for x in transports.VOITURES_MENAGES.lire(
            FIXTURES / transports.VOITURES_MENAGES.nom_fichier, REFERENTIEL
        )
        if x.niveau == "DEP"
    }
    sans = voitures[("75", 2023, ("voitures_menage", "AUCUNE"))]
    assert sans / voitures[("75", 2023, None)] > Decimal("0.6")


def _importer(connecteur):
    chemin = FIXTURES / connecteur.nom_fichier
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_pages(urls_module):
    sans_couverture = [
        dataclasses.replace(c, controle_couverture=False, tolerance_sommes=1.0)
        for c in (
            besoins.RESIDENCES_PRINCIPALES,
            transports.TRAJETS_TRAVAIL,
            transports.VOITURES_MENAGES,
        )  # fmt: skip
    ]
    for connecteur in (
        *sans_couverture,
        transports.PRIX_GAZOLE,
        transports.PRIX_SP95_E10,
        besoins.DEPENSES_MENAGES,
        transports.DEPENSE_CARBURANTS,
        energie.PRIX,
    ):
        resultat = _importer(connecteur)
        assert resultat.statut == "PUBLIE", (connecteur.nom_fichier, resultat.message)

    def valeur(indicateur, niveau="DEP", code="23"):
        serie = client.get(
            "/api/v1/series", params={"indicateur": indicateur, "niveau": niveau, "code": code}
        ).json()
        return serie["valeurs"][-1]["valeur"]

    assert valeur("PRIX_GAZOLE") == 2.165
    assert valeur("PART_TRAJET_VOITURE") == pytest.approx(81.6, abs=0.1)
    assert valeur("PART_MENAGES_SANS_VOITURE", code="75") > 60
    # Courses : environ 500 € par ménage et par mois ; carburant : environ 100 €.
    assert 350 < valeur("DEPENSE_MOIS_ALIMENTATION", "FRANCE", "FR") < 700
    assert 50 < valeur("DEPENSE_MOIS_CARBURANTS", "FRANCE", "FR") < 200

    page = client.get("/besoins/theme/transports", params={"indicateur": "PRIX_GAZOLE"})
    assert page.status_code == 200
    assert "Prix du gazole" in page.text and "2,165 €/L" in page.text
    fiche = client.get("/besoins/DEP/23").text
    assert "Transports" in fiche and "Actifs qui vont travailler en voiture" in fiche
    vue = client.get("/besoins").text
    assert "Courses alimentaires par ménage et par mois" in vue
    assert "Carburants" in vue  # hausse des prix par poste
