"""Étudiants du supérieur par formation et par discipline (exports réels, rentrées 2023-2025)."""

from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs.esr import DISCIPLINES, FORMATIONS
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={"75": "11", "92": "11", "2A": "94", "2B": "94", "971": "01"},
)
client = TestClient(app)


def _une(lignes, **criteres):
    (ligne,) = [x for x in lignes if all(getattr(x, k) == v for k, v in criteres.items())]
    return ligne.valeur


def test_formations():
    lignes = list(FORMATIONS.lire(FIXTURES / FORMATIONS.nom_fichier, REFERENTIEL))
    rentree = {"periode": date(2025, 1, 1), "niveau": "FRANCE", "code": "FR"}
    assert _une(lignes, modalite=None, **rentree) == 3103827  # hors collectivités d'outre-mer
    assert _une(lignes, modalite=("formation", "STS"), **rentree) == 393423
    # Codes départementaux du portail : « D02A » -> « 2A », « D971 » -> « 971 ».
    assert _une(lignes, niveau="DEP", code="2A", modalite=None, periode=date(2025, 1, 1)) > 0
    corse = [x for x in lignes if x.niveau == "REG" and x.code == "94" and not x.modalite]
    assert len(corse) == 3  # rentrées 2023 à 2025
    assert not [x for x in lignes if x.code in ("978", "986", "999")]


def test_disciplines():
    lignes = list(DISCIPLINES.lire(FIXTURES / DISCIPLINES.nom_fichier, REFERENTIEL))
    rentree = {"periode": date(2024, 1, 1), "niveau": "FRANCE", "code": "FR"}
    assert _une(lignes, modalite=("discipline", "LETTRES_SHS"), **rentree) == 479728
    assert _une(lignes, modalite=None, **rentree) == 1612674


def test_categorie_inconnue(tmp_path):
    chemin = tmp_path / FORMATIONS.nom_fichier
    chemin.write_text(
        "rentree;dep_id;rgp_formations_ou_etablissements;effectif\n2025;D075;Nouveauté;3\n"
    )
    with pytest.raises(FichierIllisible, match="Nouveauté"):
        list(FORMATIONS.lire(chemin, REFERENTIEL))


def test_url_d_export():
    (fichier,) = DISCIPLINES.fichiers()
    requete = parse_qs(urlparse(fichier.url).query)
    assert requete["where"] == ['etablissement_type="Université"']
    assert requete["group_by"] == ["rentree,implantation_id_departement,gd_discipline"]
    assert fichier.url.startswith("https://data.enseignementsup-recherche.gouv.fr/")


def test_import_et_api(urls_module):
    brut = config.charger().donnees_brutes
    with db.connexion("import") as conn:
        for jeu in (FORMATIONS, DISCIPLINES):
            chemin = FIXTURES / jeu.nom_fichier
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(conn, jeu, fichier, brut, chemin_local=chemin)
            assert resultat.statut == "PUBLIE", resultat.message
    paris = client.get(
        "/api/v1/repartition", params={"indicateur": "ETUDIANTS", "niveau": "DEP", "code": "75"}
    ).json()
    assert paris["annee"] == 2025 and len(paris["parts"]) == 8
    assert round(sum(p["part"] for p in paris["parts"])) == 100
    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "ETUDIANTS", "niveau": "FRANCE", "code": "FR", "debut": 2025},
    ).json()
    assert [v["valeur"] for v in serie["valeurs"]] == [3103827]
