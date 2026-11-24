"""Appli « Où va l'argent public ? », collectivités locales : comptes individuels des
départements, communes et groupements à fiscalité propre (DGFiP), additionnés par
département. Exercices 2016, 2023 à 2025."""

import json
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline, telechargement
from demographie.imports.connecteurs import EstimationsDepartements, collectivites, energie
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)
REFERENTIEL = Referentiel(identifiants={}, region_du_departement={})
CONNECTEURS = (
    (collectivites.COMPTES_DEPARTEMENTS, "departements", ("2016", "2023-2024", "2025")),
    (collectivites.COMPTES_COMMUNES, "communes", ("2016", "2023-2024", "2025")),
    (collectivites.COMPTES_GROUPEMENTS, "groupements", ("2016", "2023-2024")),
)


def _valeurs(connecteur, nom):
    lignes = connecteur.lire(FIXTURES / f"comptes-{nom}.json", REFERENTIEL)
    return {(x.indicateur, x.niveau, x.code, x.modalite[1] if x.modalite else None,
             x.periode.year): x.valeur for x in lignes}  # fmt: skip


def test_codes_des_jeux():
    assert collectivites.code_departement("001") == "01"
    assert collectivites.code_departement("02A") == "2A"
    assert collectivites.code_departement("101") == "971"
    assert collectivites.code_departement("976") == "976"


def test_totaux_france_et_postes():
    v = _valeurs(collectivites.COMPTES_DEPARTEMENTS, "departements-2025")
    assert v[("DEPENSES_DEPARTEMENT", "FRANCE", "FR", None, 2025)] == Decimal("93293.445")
    assert v[("DETTE_DEPARTEMENT", "FRANCE", "FR", None, 2025)] == Decimal("36884.622")
    # Collectivité européenne d'Alsace sous 67, plus de 68 ; Paris dans les communes.
    assert ("DEPENSES_DEPARTEMENT", "DEP", "67", None, 2025) in v
    assert ("DEPENSES_DEPARTEMENT", "DEP", "68", None, 2025) not in v
    assert ("DEPENSES_DEPARTEMENT", "DEP", "75", None, 2025) not in v
    postes = [m for (i, n, c, m, a) in v if n == "DEP" and c == "01" and m]
    total = v[("DEPENSES_DEPARTEMENT", "DEP", "01", None, 2025)]
    somme = sum(v[("DEPENSES_DEPARTEMENT", "DEP", "01", m, 2025)] for m in postes)
    assert len(postes) == 6 and abs(somme - total) < Decimal("0.01")

    c = _valeurs(collectivites.COMPTES_COMMUNES, "communes-2023-2024")
    assert c[("DEPENSES_COMMUNES", "FRANCE", "FR", None, 2024)] == Decimal("124033.511")
    assert c[("DETTE_COMMUNES", "FRANCE", "FR", None, 2024)] == Decimal("66527.930")
    g = _valeurs(collectivites.COMPTES_GROUPEMENTS, "groupements-2023-2024")
    assert g[("DEPENSES_INTERCO", "FRANCE", "FR", None, 2024)] == Decimal("81245.511")
    assert g[("DETTE_INTERCO", "FRANCE", "FR", None, 2025)] == Decimal("56400.434")
    assert all(x >= 0 for k, x in v.items() if k[3] is None)


def test_colonne_absente_et_doublon(tmp_path):
    lignes = json.loads((FIXTURES / "comptes-communes-2025.json").read_text(encoding="utf-8"))
    chemin = tmp_path / "comptes-communes-2025.json"
    sans_remb = [{k: v for k, v in x.items() if k != "remb"} for x in lignes]
    chemin.write_text(json.dumps(sans_remb), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="remb"):
        list(collectivites.COMPTES_COMMUNES.lire(chemin, REFERENTIEL))
    chemin.write_text(json.dumps(lignes + lignes[:1]), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="double"):
        list(collectivites.COMPTES_COMMUNES.lire(chemin, REFERENTIEL))


def test_decouverte_des_jeux(monkeypatch):
    prefixe = collectivites.COMMUNES.prefixe
    catalogue = {"results": [{"dataset_id": prefixe + a}
                             for a in ("2012", "2016", "2017-2018", "2023-2024")]}  # fmt: skip
    monkeypatch.setattr(telechargement, "lire_page", lambda url: json.dumps(catalogue))
    fichiers = collectivites.COMPTES_COMMUNES.fichiers()
    assert [f.nom for f in fichiers] == [
        "comptes-communes-2016.json",
        "comptes-communes-2017-2018.json",
        "comptes-communes-2023-2024.json",
    ]
    assert "group_by=an%2C+dep" in fichiers[0].url
    assert collectivites.COMPTES_COMMUNES.accepte("comptes-communes-2017-2018.json")
    assert not collectivites.COMPTES_COMMUNES.accepte("comptes-departements-2016.json")


def _importer(connecteur, chemin):
    with db.connexion("import") as conn:
        fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_pages(urls_module):
    etapes = [
        (EstimationsDepartements(), FIXTURES / "estim-pop-dep-sexe-aq-1975-2026.xlsx"),
        (energie.PRIX, FIXTURES / energie.PRIX.nom_fichier),
    ]
    for connecteur, nom, millesimes in CONNECTEURS:
        etapes += [(connecteur, FIXTURES / f"comptes-{nom}-{m}.json") for m in millesimes]
    for connecteur, chemin in etapes:
        resultat = _importer(connecteur, chemin)
        assert resultat.statut == "PUBLIE", f"{chemin.name} : {resultat.message}"

    with db.connexion("lecture") as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM api.serie WHERE indicateur = 'DEPENSES_COMMUNES'"
            " AND niveau = 'DEP' AND periode = %s",
            (date(2024, 1, 1),),
        ).fetchone()["n"]
    assert n == 101

    accueil = client.get("/argent-public").text
    assert "/argent-public/DEP/23" in accueil
    assert "Mon département" in accueil

    page = client.get("/argent-public/DEP/23")
    assert page.status_code == 200
    texte = page.text
    assert "L'argent public local : Creuse" in texte
    assert "Dépense locale par habitant, 2025" in texte
    assert "Aides sociales" in texte
    assert 'id="historique-local"' in texte

    alsace = client.get("/argent-public/DEP/68").text
    assert "Collectivité européenne d&#39;Alsace" in alsace
    assert "Le département (la Collectivité européenne d&#39;Alsace), poste" in alsace
    paris = client.get("/argent-public/DEP/75").text
    assert "Paris est à la fois une commune et un département" in paris
    assert client.get("/argent-public/DEP/99").status_code == 404
