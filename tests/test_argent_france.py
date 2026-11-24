"""Appli « Où va l'argent public ? », vue France : tableaux des comptes nationaux de l'INSEE
(édition 2025 ; dépenses par fonction de l'édition 2024) et dette trimestrielle (BDM)."""

from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline, telechargement
from demographie.imports.connecteurs import CONNECTEURS, comptes_publics
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
COMPTES = (comptes_publics.TableauComptes, comptes_publics.DetteTrimestrielle)
REFERENTIEL = Referentiel(identifiants={}, region_du_departement={})


def _valeurs(connecteur):
    chemin = FIXTURES / connecteur.nom_fichier
    return {
        (x.indicateur, x.modalite[1] if x.modalite else None, x.periode): x
        for x in connecteur.lire(chemin, REFERENTIEL)
    }


def _an(annee: int):
    from datetime import date

    return date(annee, 1, 1)


def test_chiffres_publies_par_l_insee():
    depenses = _valeurs(comptes_publics.DEPENSES_RECETTES)
    assert depenses[("DEPENSES_APU", None, _an(2025))].valeur == Decimal("1714.1117")
    assert depenses[("RECETTES_APU", None, _an(2025))].valeur == Decimal("1562.5197")
    assert round(depenses[("DEPENSES_APU_PIB", None, _an(2025))].valeur, 1) == Decimal("57.3")
    dette = _valeurs(comptes_publics.DETTE)
    assert dette[("DETTE_APU", None, _an(2025))].valeur == Decimal("3460.1")
    assert dette[("DETTE_APU_PIB", None, _an(2025))].valeur == Decimal("115.7")
    solde = _valeurs(comptes_publics.SOLDE)
    assert solde[("SOLDE_APU", None, _an(2025))].valeur == Decimal("-151.592")
    assert solde[("SOLDE_APU_PIB", None, _an(2025))].valeur == Decimal("-5.1")
    po = _valeurs(comptes_publics.PRELEVEMENTS)
    assert po[("PRELEVEMENTS_OBLIGATOIRES", None, _an(2025))].valeur == Decimal("1305.067")
    # Les trois dernières années sont provisoires.
    assert dette[("DETTE_APU", None, _an(2023))].statut == "PROVISOIRE"
    assert dette[("DETTE_APU", None, _an(2022))].statut == "DEFINITIF"


def test_recettes_par_nature_et_reste():
    v = _valeurs(comptes_publics.RECETTES_NATURE)
    total = v[("RECETTE_NATURE", None, _an(2025))].valeur
    parts = [v[("RECETTE_NATURE", m, _an(2025))].valeur
             for m in ("COTISATIONS", "PRODUCTION", "REVENU_PATRIMOINE", "AUTRES")]  # fmt: skip
    assert sum(parts) == total == Decimal("1562.5197")
    assert v[("RECETTE_NATURE", "AUTRES", _an(2025))].valeur == Decimal("203.4697")
    assert v[("CHARGE_INTERETS", None, _an(2025))].valeur == Decimal("65.7209")


def test_fonctions_et_etages_somment_au_total():
    f = _valeurs(comptes_publics.FONCTIONS_APU)
    total = f[("DEPENSE_FONCTION", None, _an(2024))].valeur
    assert total == Decimal("1671.794")
    fonctions = [x.valeur for (i, m, p), x in f.items() if m and p == _an(2024)]
    assert len(fonctions) == 10
    assert abs(sum(fonctions) - total) < Decimal("0.01")
    e = _valeurs(comptes_publics.ETAGES_APU)
    etages = [e[("DEPENSE_ETAGE", m, _an(2024))].valeur for m in ("CENTRALE", "LOCALE", "SECU")]
    assert sum(etages) == e[("DEPENSE_ETAGE", None, _an(2024))].valeur == total


def test_dette_trimestrielle():
    lignes = list(
        comptes_publics.DETTE_TRIMESTRIELLE.lire(
            FIXTURES / comptes_publics.DETTE_TRIMESTRIELLE.nom_fichier, REFERENTIEL
        )
    )
    derniere = max((x for x in lignes if x.indicateur == "DETTE_TRIMESTRIELLE"),
                   key=lambda x: x.periode)  # fmt: skip
    assert (derniere.periode.isoformat(), derniere.valeur) == ("2026-04-01", Decimal("3595.5"))
    assert derniere.periode_type == "TRIMESTRE"


def test_ligne_renommee(tmp_path):
    """Un libellé de ligne changé : le tableau est rejeté, pas lu à moitié."""
    import openpyxl

    classeur = openpyxl.load_workbook(FIXTURES / "t_3215.xlsx")
    feuille = classeur.worksheets[-1]
    for rang in feuille.iter_rows():
        for cellule in rang:
            if isinstance(cellule.value, str) and cellule.value.strip().endswith("Recettes"):
                cellule.value = "Ressources"
    chemin = tmp_path / "t_3215.xlsx"
    classeur.save(chemin)
    with pytest.raises(FichierIllisible, match="RECETTES_APU"):
        list(comptes_publics.DEPENSES_RECETTES.lire(chemin, REFERENTIEL))


def test_decouverte_par_le_sommaire(monkeypatch):
    pages = {
        comptes_publics.PAGE_STABLE: '<a href="/fr/statistiques/900">Chiffres détaillés</a>',
        "https://www.insee.fr/fr/statistiques/900": (
            '<a href="/fr/statistiques/901">Dette et déficit publics au sens de Maastricht</a>'
        ),
        "https://www.insee.fr/fr/statistiques/901": (
            '<a href="/fr/statistiques/fichier/901/t_3101_fr.xlsx">Tableau</a>'
        ),
        # Dépenses par fonction : absentes de l'édition en cours, lues dans la précédente.
        "https://www.insee.fr/fr/statistiques/8574832": (
            '<a href="/fr/statistiques/8574707">Dépenses des administrations publiques '
            "ventilées par fonction</a>"
        ),
        "https://www.insee.fr/fr/statistiques/8574707": (
            '<a href="/fr/statistiques/fichier/8574707/T_3301.xlsx">Tableau</a>'
        ),
    }
    monkeypatch.setattr(telechargement, "lire_page", lambda url: pages.get(url, ""))
    (dette,) = comptes_publics.DETTE.fichiers()
    assert dette.url == "https://www.insee.fr/fr/statistiques/fichier/901/t_3101_fr.xlsx"
    assert dette.nom == "t_3101.xlsx"
    (fonctions,) = comptes_publics.FONCTIONS_APU.fichiers()
    assert fonctions.url.endswith("/8574707/T_3301.xlsx")


def test_import_et_page(urls_module):
    with db.connexion("import") as conn:
        for connecteur in CONNECTEURS["argent"]:
            if not isinstance(connecteur, COMPTES):
                continue  # budget de l'État : tests/test_argent_etat.py
            chemin = FIXTURES / connecteur.nom_fichier
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(
                conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
            )
            assert resultat.statut == "PUBLIE", resultat.message
    serie = client.get(
        "/api/v1/series", params={"indicateur": "SOLDE_APU", "niveau": "FRANCE", "code": "FR"}
    ).json()
    assert serie["valeurs"][-1]["valeur"] == -151.592
    indicateurs = client.get("/api/v1/indicateurs", params={"rubrique": "ARGENT"}).json()
    assert len([i for i in indicateurs if i["theme"] in {"DEPENSES", "RECETTES", "DETTE"}]) == 16

    page = client.get("/argent-public")
    assert page.status_code == 200
    texte = page.text
    assert "1 714 Md€" in texte  # dépense publique 2025
    assert "3 596 Md€" in texte  # dette au 2e trimestre 2026
    assert "2e trimestre 2026" in texte
    assert "Déficit 2025" in texte
    assert "Pour 1 000 € de dépense publique" in texte
    assert "Emprunt (le déficit)" in texte
    assert 'id="deficit-dette"' in texte
    accueil = client.get("/").text
    assert "/argent-public" in accueil


def test_page_sans_donnees(urls_db):
    page = client.get("/argent-public")
    assert page.status_code == 200
    assert "pas encore importés" in page.text
