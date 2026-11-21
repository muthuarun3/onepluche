"""Pipeline d'import de bout en bout sur une base dédiée, puis API et pages.

Les tests de ce module s'enchaînent : base vide, imports refusés, imports publiés,
lecture, puis révision soumise à validation.
"""

import shutil
from decimal import Decimal

import openpyxl
import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import cli, config, db
from demographie.app import app
from demographie.catalogue.references import REFERENCES_INSEE
from demographie.imports import pipeline
from demographie.imports.connecteurs.estimations import (
    EstimationsDepartements,
    EstimationsRegions,
)
from demographie.imports.modele import Fichier

NOM_DEP = "estim-pop-dep-sexe-aq-1975-2026.xlsx"
NOM_REG = "estim-pop-nreg-sexe-aq-1975-2026.xlsx"
client = TestClient(app)


def _importer(connecteur, chemin):
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def _modifier(tmp_path, nom, feuille, code, facteur, colonnes=None):
    """Copie d'un fichier de test où une ligne est multipliée par un facteur."""
    classeur = openpyxl.load_workbook(FIXTURES / nom)
    for rang in classeur[feuille].iter_rows():
        if str(rang[0].value).strip() == code:
            for i, cellule in enumerate(rang):
                if isinstance(cellule.value, int) and (colonnes is None or i in colonnes):
                    cellule.value = round(cellule.value * facteur)
    dossier = tmp_path / "modifie"
    dossier.mkdir(exist_ok=True)
    chemin = dossier / nom
    classeur.save(chemin)
    return chemin


def _observation(code, niveau="DEP", annee=2026):
    with db.connexion("import") as conn:
        return conn.execute(
            """SELECT o.valeur, o.import_id FROM stat.observation o
               JOIN ref.territoire t USING (territoire_id)
               WHERE t.code = %s AND t.niveau = %s AND o.periode = make_date(%s, 1, 1)
                 AND o.sexe = 'T' AND o.age_min IS NULL""",
            (code, niveau, annee),
        ).fetchone()


def test_fichier_incoherent_rejete(urls_module, tmp_path):
    # Total de Paris modifié sans ses tranches d'âge : la somme des âges ne colle plus.
    chemin = _modifier(tmp_path, NOM_DEP, "2026", "75", 1.1, colonnes={22})
    resultat = _importer(EstimationsDepartements(), chemin)
    assert resultat.statut == "REJETE"
    assert "somme des âges" in resultat.message
    assert _observation("75") is None


def test_territoire_inconnu_rejete(urls_module, tmp_path):
    classeur = openpyxl.load_workbook(FIXTURES / NOM_REG)
    for rang in classeur["2026"].iter_rows(min_col=1, max_col=1):
        if rang[0].value == "Bretagne":
            rang[0].value = "Armorique"
    chemin = tmp_path / NOM_REG
    classeur.save(chemin)
    resultat = _importer(EstimationsRegions(), chemin)
    assert resultat.statut == "REJETE"
    assert "Territoires inconnus : REG/Armorique" in resultat.message


def test_import_publie(urls_module):
    resultat = _importer(EstimationsDepartements(), FIXTURES / NOM_DEP)
    assert resultat.statut == "PUBLIE", resultat.message
    with db.connexion("import") as conn:
        journal = conn.execute(
            "SELECT * FROM ingest.import WHERE import_id = %s", (resultat.import_id,)
        ).fetchone()
        restantes = conn.execute("SELECT count(*) AS n FROM ingest.ligne").fetchone()["n"]
    assert journal["lignes_chargees"] > 30_000
    assert restantes == 0
    assert (config.charger().donnees_brutes / f"{journal['sha256']}.xlsx").exists()
    assert _observation("75")["valeur"] == 2_047_602


def test_meme_fichier_non_reimporte(urls_module):
    resultat = _importer(EstimationsDepartements(), FIXTURES / NOM_DEP)
    assert resultat.statut == "DEJA_IMPORTE"


def test_import_regions(urls_module):
    import_france = _observation("FR", "FRANCE")["import_id"]
    resultat = _importer(EstimationsRegions(), FIXTURES / NOM_REG)
    assert resultat.statut == "PUBLIE", resultat.message
    assert _observation("24", "REG")["valeur"] == 2_589_286
    # La France reste celle du fichier départemental.
    assert _observation("FR", "FRANCE")["import_id"] == import_france


@pytest.mark.parametrize("reference", REFERENCES_INSEE, ids=lambda r: r.libelle)
def test_chiffres_identiques_a_l_insee(urls_module, reference):
    """Contrôle de sortie de la phase 1, à travers l'API publique."""
    parametres = {"niveau": reference.niveau, "code": reference.code, "debut": reference.annee,
                  "fin": reference.annee}  # fmt: skip
    pop = client.get("/api/v1/series", params={"indicateur": "POP", **parametres}).json()
    part = client.get("/api/v1/series", params={"indicateur": "PART_60_PLUS", **parametres})
    assert pop["valeurs"][0]["valeur"] == reference.population
    assert round(Decimal(str(part.json()["valeurs"][0]["valeur"])), 1) == Decimal(
        str(reference.part_60_plus)
    )


def test_commande_verifier(urls_module, capsys):
    assert cli.main(["verifier"]) == 0
    assert "ÉCART" not in capsys.readouterr().out


def test_api_indicateurs(urls_module):
    indicateurs = client.get("/api/v1/indicateurs").json()
    assert [i["code"] for i in indicateurs][:2] == ["POP", "PART_MOINS_20"]
    assert indicateurs[0]["source_code"] == "INSEE_EST"
    assert indicateurs[0]["mis_a_jour_le"] is not None


def test_api_serie(urls_module):
    serie = client.get(
        "/api/v1/series", params={"indicateur": "POP", "niveau": "DEP", "code": "75"}
    ).json()
    assert [v["annee"] for v in serie["valeurs"]] == [1975, 1995, 2024, 2025, 2026]
    assert serie["valeurs"][-1] == {
        "annee": 2026,
        "periode": "2026-01-01",
        "periode_type": "1ER_JANVIER",
        "valeur": 2047602,
        "provisoire": True,
    }
    assert serie["territoire"]["libelle"] == "Paris"
    assert serie["indicateur"]["source_url"].startswith("https://www.insee.fr/")


def test_api_structure(urls_module):
    reponse = client.get("/api/v1/structure", params={"niveau": "DEP", "code": "75"}).json()
    assert reponse["annee"] == 2026 and reponse["provisoire"] is True
    assert len(reponse["tranches"]) == 20
    total = sum(t["hommes"] + t["femmes"] for t in reponse["tranches"])
    assert total == 2_047_602
    ancien = client.get(
        "/api/v1/structure", params={"niveau": "DEP", "code": "971", "annee": 1995}
    ).json()
    assert ancien["tranches"][-1]["age_min"] == 90 and ancien["tranches"][-1]["age_max"] is None


@pytest.mark.parametrize(
    ("url", "attendu"),
    [
        ("/api/v1/series?indicateur=INCONNU&niveau=DEP&code=75", 404),
        ("/api/v1/series?indicateur=POP&niveau=DEP&code=99", 404),
        ("/api/v1/series?indicateur=POP&niveau=DEP&code=75;DROP", 422),
        ("/api/v1/structure?niveau=DEP&code=976&annee=1995", 404),
        ("/territoire/DEP/99", 404),
        ("/territoire/COMMUNE/75056", 422),
    ],
)
def test_erreurs(urls_module, url, attendu):
    assert client.get(url).status_code == attendu


def test_pages(urls_module):
    accueil = client.get("/")
    assert accueil.status_code == 200
    # Accueil : le texte d'introduction et un lien par question ; barre latérale.
    assert "Muthu" in accueil.text and 'href="/francais"' in accueil.text
    assert 'href="/besoins"' in accueil.text and "Quel âge" not in accueil.text
    francais = client.get("/francais")
    assert francais.status_code == 200
    assert 'href="/territoire/DEP/23"' in francais.text
    assert '<a href="/francais" aria-current="page">' in francais.text
    # Résumé : seuls les blocs dont les données sont importées apparaissent.
    assert "Quel âge avons-nous ?" in francais.text
    assert "Quels métiers ?" not in francais.text
    page = client.get("/territoire/DEP/23")
    assert page.status_code == 200
    assert "Creuse" in page.text and "40,8&nbsp;%" in page.text
    assert "script-src 'self'" in page.headers["Content-Security-Policy"]
    assert client.get("/static/echarts.min.js").status_code == 200


def test_revision_importante_attend_validation(urls_module, tmp_path):
    # Toute la ligne de Paris augmente de 10 % : cohérente, mais suspecte.
    chemin = _modifier(tmp_path, NOM_DEP, "2026", "75", 1.1)
    resultat = _importer(EstimationsDepartements(), chemin)
    assert resultat.statut == "EN_ATTENTE", resultat.message
    assert "DEP 75 2026" in resultat.message
    assert _observation("75")["valeur"] == 2_047_602
    with db.connexion("import") as conn:
        with pytest.raises(pipeline.ImportImpossible):
            pipeline.valider(conn, resultat.import_id - 1)
        pipeline.valider(conn, resultat.import_id)
    assert _observation("75")["valeur"] == round(2_047_602 * 1.1)
    paris = client.get(
        "/api/v1/series",
        params={"indicateur": "POP", "niveau": "DEP", "code": "75", "debut": 2026},
    ).json()
    assert paris["valeurs"][0]["valeur"] == _observation("75")["valeur"]


def test_fichier_corrige_apres_rejet(urls_module, tmp_path):
    """Un fichier rejeté (ex. bogue du connecteur) peut être réimporté tel quel."""
    with db.connexion("import") as conn:
        conn.execute(
            "UPDATE ingest.import SET statut = 'REJETE' WHERE fichier_nom = %s "
            "AND statut = 'PUBLIE' AND import_id = (SELECT min(import_id) FROM ingest.import "
            "WHERE statut = 'PUBLIE')",
            (NOM_DEP,),
        )
    copie = tmp_path / NOM_DEP
    shutil.copyfile(FIXTURES / NOM_DEP, copie)
    resultat = _importer(EstimationsDepartements(), copie)
    assert resultat.statut == "EN_ATTENTE"  # Paris revient de +10 % à la valeur INSEE
