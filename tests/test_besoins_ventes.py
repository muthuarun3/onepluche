"""Appli 2, phase B : prix de vente (DVF, extrait réel de la Creuse) et parc social (RPLS)."""

import csv
import dataclasses
import gzip
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline, telechargement
from demographie.imports.connecteurs import dvf, rpls
from demographie.imports.connecteurs.besoins import NIVEAU_DE_VIE
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel({}, region_du_departement={"23": "75", "75": "11", "971": "01"})
COLONNES = [
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "code_commune",
    "code_departement", "type_local", "surface_reelle_bati", "id_parcelle", "lot1_numero",
]  # fmt: skip


def _dvf(tmp_path, ventes, nom="dvf-2025.csv.gz"):
    """Fichier DVF minimal : une ligne par (id, nature, prix, département, type, surface)."""
    chemin = tmp_path / nom
    with gzip.open(chemin, "wt", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(COLONNES)
        for ident, nature, prix, dep, type_local, surface, *reste in ventes:
            jour = reste[0] if reste else "2025-06-01"
            ecrivain.writerow(
                [ident, jour, nature, prix, f"{dep}001", dep, type_local, surface, f"p{ident}", ""]
            )
    return chemin


def _retenues(chemin):
    return [(v.departement, v.type_logement, round(v.prix_m2)) for v, _ in dvf._ventes(chemin)]


def test_regles_de_selection_des_ventes(tmp_path):
    chemin = _dvf(
        tmp_path,
        [
            ("1", "Vente", "100000", "23", "Maison", "100"),  # retenue
            ("1", "Vente", "100000", "23", "Maison", "100"),  # même maison, autre parcelle
            ("1", "Vente", "100000", "23", "Dépendance", ""),  # garage admis
            ("2", "Vente", "200000", "23", "Appartement", "50"),
            ("2", "Vente", "200000", "23", "Appartement", "30"),  # deux logements : écartée
            ("3", "Vente", "90000", "23", "Maison", "90"),
            ("3", "Vente", "90000", "23", "Local industriel. commercial ou assimilé", "40"),
            ("4", "Echange", "50000", "23", "Maison", "50"),  # pas une vente
            ("5", "Vente", "30000", "23", "Appartement", "8"),  # moins de 9 m²
            ("6", "Vente", "900", "23", "Maison", "40"),  # moins de 1 000 €
            ("7", "Vente", "150000", "75", "Appartement", "15"),
        ],
    )
    assert _retenues(chemin) == [("23", "MAISON", 1000), ("75", "APPARTEMENT", 10000)]


def test_lignes_d_une_vente_dispersees(tmp_path):
    chemin = _dvf(
        tmp_path,
        [
            ("1", "Vente", "1000", "23", "Maison", "10"),
            ("2", "Vente", "1000", "23", "Maison", "10"),
            ("1", "Vente", "1000", "23", "Maison", "10"),
        ],
    )
    with pytest.raises(FichierIllisible, match="dispersées"):
        _retenues(chemin)


def test_mediane_tronquee():
    assert dvf.mediane_tronquee([1000.0] * 29) is None
    # 100 ventes : la plus basse et la plus haute sont écartées.
    prix = [1.0] + [2000.0] * 49 + [3000.0] * 49 + [1e9]
    assert dvf.mediane_tronquee(prix) == 2500


def test_annee_du_fichier(tmp_path):
    ventes = [(str(i), "Vente", "100000", "23", "Maison", "100", "2024-12-31") for i in range(40)]
    with pytest.raises(FichierIllisible, match="Vente du 2024-12-31 dans le fichier 2025"):
        list(dvf.VENTES.lire(_dvf(tmp_path, ventes), REFERENTIEL))


def test_annee_incomplete_provisoire(tmp_path):
    ventes = [(str(i), "Vente", 100000 + i, "23", "Maison", "100") for i in range(40)]
    lignes = list(dvf.VENTES.lire(_dvf(tmp_path, ventes), REFERENTIEL))
    assert {x.statut for x in lignes} == {"PROVISOIRE"}  # dernière vente en juin


def test_prix_de_la_creuse():
    lignes = {
        (x.niveau, x.code, x.modalite): x
        for x in dvf.VENTES.lire(FIXTURES / "dvf-2025.csv.gz", REFERENTIEL)
    }
    assert lignes[("DEP", "23", None)].valeur == 853
    assert lignes[("DEP", "23", ("type_logement", "APPARTEMENT"))].valeur == 857
    assert lignes[("DEP", "23", None)].statut == "DEFINITIF"
    assert ("REG", "75", None) in lignes and ("FRANCE", "FM", None) in lignes


def test_decouverte_des_annees_dvf(monkeypatch):
    page = '<a href="../">..</a><a href="/geo-dvf/latest/csv/2021/">2021/</a>' + "".join(
        f'<a href="/geo-dvf/latest/csv/{a}/">{a}/</a>' for a in (2022, 2025)
    )
    monkeypatch.setattr(telechargement, "lire_page", lambda _url: page)
    fichiers = dvf.VENTES.fichiers()
    assert [f.nom for f in fichiers] == ["dvf-2021.csv.gz", "dvf-2022.csv.gz", "dvf-2025.csv.gz"]
    assert fichiers[-1].url.endswith("/2025/full.csv.gz")


def _rpls(tmp_path, departements, nom="rpls-2025.csv"):
    chemin = tmp_path / nom
    chemin.write_text('"DEP_CODE"\n' + "".join(f'"{d}"\n' for d in departements), "utf-8")
    return chemin


def test_parc_social(tmp_path):
    chemin = _rpls(tmp_path, ["23"] * 3 + ["75"] * 5 + ["971"] * 2)
    lignes = {(x.niveau, x.code): x.valeur for x in rpls.PARC_SOCIAL.lire(chemin, REFERENTIEL)}
    assert lignes == {
        ("DEP", "23"): 3, ("DEP", "75"): 5, ("DEP", "971"): 2, ("REG", "75"): 3,
        ("REG", "11"): 5, ("REG", "01"): 2, ("FRANCE", "FR"): 10, ("FRANCE", "FM"): 8,
    }  # fmt: skip


def test_parc_social_sans_departement(tmp_path):
    with pytest.raises(FichierIllisible, match="1 logements sans département"):
        list(rpls.PARC_SOCIAL.lire(_rpls(tmp_path, ["23"] * 10 + [""]), REFERENTIEL))


def test_decouverte_des_millesimes_rpls(monkeypatch):
    monkeypatch.setattr(telechargement, "lire_json", lambda _url: {"millesime": "2025-01"})
    fichiers = rpls.PARC_SOCIAL.fichiers()
    assert [f.nom for f in fichiers] == [f"rpls-{a}.csv" for a in range(2022, 2026)]
    assert "millesime=2025-01" in fichiers[-1].url and "columns=DEP_CODE" in fichiers[-1].url


def _importer(connecteur, chemin):
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_api(urls_module, tmp_path):
    # Extraits : un département seulement, la couverture ne peut pas être complète.
    sans_couverture = {"controle_couverture": False}
    for connecteur, chemin in (
        (NIVEAU_DE_VIE, FIXTURES / NIVEAU_DE_VIE.nom_fichier),
        (dvf.VENTES, FIXTURES / "dvf-2025.csv.gz"),
        (rpls.PARC_SOCIAL, _rpls(tmp_path, ["23"] * 3 + ["75"] * 5)),
    ):
        connecteur = dataclasses.replace(connecteur, **sans_couverture)
        resultat = _importer(connecteur, chemin)
        assert resultat.statut == "PUBLIE", resultat.message

    def derniere(indicateur, niveau="DEP", code="23"):
        reponse = client.get(
            "/api/v1/series", params={"indicateur": indicateur, "niveau": niveau, "code": code}
        )
        return reponse.json()["valeurs"][-1]

    assert derniere("PRIX_VENTE_M2")["valeur"] == 853
    # 60 m² × 853 €/m² / 23 210 € de niveau de vie médian (Filosofi 2023).
    annees = derniere("ANNEES_REVENU_60M2")
    assert annees["annee"] == 2025 and Decimal(str(annees["valeur"])) == Decimal("2.2")
    assert derniere("LOGEMENTS_SOCIAUX", "FRANCE", "FR")["valeur"] == 8
    assert derniere("LOGEMENTS_SOCIAUX")["periode_type"] == "1ER_JANVIER"
