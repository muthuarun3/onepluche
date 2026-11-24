"""Retraités et minimum vieillesse (DREES, extraits réels de l'édition 2026)."""

from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline, telechargement
from demographie.imports.connecteurs.drees import EACR, MINIMUM_VIEILLESSE
from demographie.imports.connecteurs.recensement import RECENSEMENT
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

CLASSEUR = FIXTURES / "62_eacr_diffusee_part_1_version_du_26_mai_2026.xlsx"
CSV = FIXTURES / "panorama-minimum-vieillesse.csv"
RP = FIXTURES / "DS_RP_EMPLOI_LR_PRINC.json"
REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={
        "75": "11",
        "92": "11",
        "976": "06",
        "971": "01",
        "2A": "94",
        "2B": "94",
    },  # fmt: skip
)
client = TestClient(app)


def _une(lignes, **criteres):
    (ligne,) = [x for x in lignes if all(getattr(x, k) == v for k, v in criteres.items())]
    return ligne


def test_retraites_tous_regimes():
    lignes = list(EACR.lire(CLASSEUR, REFERENTIEL))
    fin_2024 = {"periode": date(2024, 1, 1), "niveau": "FRANCE", "code": "FR"}
    # DREES, EACR 2024, retraités résidant en France, tous régimes.
    assert _une(lignes, indicateur="PENSIONNES", sexe="T", **fin_2024).valeur == 16903772
    assert _une(lignes, indicateur="PENSIONNES", sexe="F", **fin_2024).valeur == 9312686
    assert _une(lignes, indicateur="PENSIONNES", sexe="H", **fin_2024).valeur == 7591086
    # Pension moyenne de droit direct, brute, par mois (lue pour la rubrique VIVRE).
    assert _une(lignes, indicateur="PENSION_MOYENNE", sexe="T", **fin_2024).valeur == Decimal(
        "1705"
    )
    femmes, hommes = (
        _une(lignes, indicateur="PENSION_MOYENNE", sexe=s, **fin_2024).valeur for s in "FH"
    )
    assert femmes < hommes
    assert {x.niveau for x in lignes} == {"FRANCE"}
    assert {x.periode.year for x in lignes} == set(range(2019, 2025))
    # Années × (deux effectifs + pension moyenne) × sexes, lignes CNAV ignorées.
    assert len(lignes) == 6 * 3 * 3


def test_classeur_sans_la_feuille(tmp_path):
    from openpyxl import Workbook

    chemin = tmp_path / "x.xlsx"
    Workbook().save(chemin)
    with pytest.raises(FichierIllisible, match="A-Cadrage"):
        list(EACR.lire(chemin, REFERENTIEL))


def test_decouverte_du_classeur(monkeypatch):
    base = "https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets"
    noms = (
        "documentationeacr_mai2026_pdf",
        "62_eacr_diffusee_part_2_version_du_26_mai_2026_xlsx",
        "62_eacr_diffusee_part_1_version_du_26_mai_2026_xlsx",
    )
    pieces = {"attachments": [{"href": f"{base}/donnes_eacr/attachments/{n}"} for n in noms]}
    monkeypatch.setattr(telechargement, "lire_json", lambda url: pieces)
    (fichier,) = EACR.fichiers()
    assert fichier.nom == CLASSEUR.name and fichier.millesime == "26_mai_2026"
    assert fichier.url.endswith("part_1_version_du_26_mai_2026_xlsx")


def test_minimum_vieillesse():
    lignes = list(MINIMUM_VIEILLESSE.lire(CSV, REFERENTIEL))
    en_2024 = {"periode": date(2024, 1, 1)}
    mv = {"indicateur": "MIN_VIEILLESSE", **en_2024}
    assert _une(lignes, niveau="DEP", code="75", **mv).valeur == 32804
    assert _une(lignes, niveau="FRANCE", code="FR", **mv).valeur == 752699
    assert _une(lignes, niveau="FRANCE", code="FM", **mv).valeur == 683641
    assert _une(lignes, niveau="REG", code="94", **mv).valeur == 7860  # Corse, une fois
    assert _une(lignes, niveau="REG", code="06", **mv).valeur == 31  # Mayotte, reprise
    taux = _une(lignes, niveau="DEP", code="75", indicateur="TAUX_MIN_VIEILLESSE_60P", **en_2024)
    assert taux.valeur == Decimal("6.54")  # publié 0,0654
    codes = {x.code for x in lignes if x.niveau == "DEP"}
    assert len(codes) == 101 and not codes & {"69D", "69M", "6AE", "20R", "975", "1000"}


def test_import_et_api(urls_module):
    brut = config.charger().donnees_brutes
    with db.connexion("import") as conn:
        for connecteur, chemin in ((EACR, CLASSEUR), (MINIMUM_VIEILLESSE, CSV), (RECENSEMENT, RP)):
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(conn, connecteur, fichier, brut, chemin_local=chemin)
            assert resultat.statut == "PUBLIE", resultat.message
    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "PENSIONNES", "niveau": "FRANCE", "code": "FR", "debut": 2024},
    ).json()
    assert [v["valeur"] for v in serie["valeurs"]] == [16903772]
    assert "Ancêtre" in serie["indicateur"]["avertissement"]
    paris = client.get(
        "/api/v1/series",
        params={"indicateur": "MIN_VIEILLESSE", "niveau": "DEP", "code": "75"},
    ).json()
    assert [v["valeur"] for v in paris["valeurs"]] == [29742, 31350, 32804]
    rapport = client.get(
        "/api/v1/series",
        params={"indicateur": "PENSIONNES_POUR_100_ACTIFS", "niveau": "FRANCE", "code": "FR"},
    ).json()
    # 16 760 138 retraités fin 2023 pour 31,8 millions d'actifs de 15 à 64 ans (RP 2023).
    assert [(v["annee"], v["valeur"]) for v in rapport["valeurs"]] == [(2023, 52.7)]
