"""Appli 3, phase A1 : catalogue VIVRE, Filosofi détaillé et salaires (extraits Melodi)."""

import dataclasses
import json
from datetime import date

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS, vivre
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(identifiants={})
JEUX = (vivre.REVENUS_FILOSOFI, vivre.SALAIRES_CATEGORIES, vivre.SALAIRES_AGES)
client = TestClient(app)


def _lignes(jeu, code, annee):
    # « 75 » est à la fois Paris et la Nouvelle-Aquitaine : on lit les départements.
    niveau = "FRANCE" if code in ("FR", "FM") else "DEP"
    return [
        x
        for x in jeu.lire(FIXTURES / jeu.nom_fichier, REFERENTIEL)
        if x.niveau == niveau and x.code == code and x.periode == date(annee, 1, 1)
    ]


def test_filosofi_detaille_de_la_creuse():
    creuse = {x.indicateur: float(x.valeur) for x in _lignes(vivre.REVENUS_FILOSOFI, "23", 2023)}
    assert len(creuse) == 14
    assert creuse["NIVEAU_VIE_D1"] == 12380
    assert creuse["NIVEAU_VIE_D9"] == 37240
    assert creuse["RAPPORT_D9_D1"] == pytest.approx(3.0)
    assert creuse["INDICE_GINI"] == pytest.approx(0.253)
    assert creuse["PART_PENSIONS"] == pytest.approx(40.2)
    # Impôts directs comptés en positif (le producteur publie -12,4).
    assert creuse["PART_IMPOTS"] == pytest.approx(12.4)
    # Pas de total France entière : la France métropolitaine seulement.
    assert _lignes(vivre.REVENUS_FILOSOFI, "FM", 2023)
    assert not _lignes(vivre.REVENUS_FILOSOFI, "FR", 2023)
    assert _lignes(vivre.REVENUS_FILOSOFI, "974", 2023)


def test_salaires_par_sexe_et_categorie():
    paris = {
        (x.sexe, x.modalite[1] if x.modalite else "TOUS"): x.valeur
        for x in _lignes(vivre.SALAIRES_CATEGORIES, "75", 2024)
    }
    assert paris[("T", "TOUS")] == 3836
    assert len(paris) == 15  # 3 sexes × (4 catégories + total)
    assert paris[("H", "CADRES_DIRIGEANTS")] > paris[("F", "CADRES_DIRIGEANTS")]
    france = {
        x.sexe: x.valeur for x in _lignes(vivre.SALAIRES_CATEGORIES, "FR", 2024) if not x.modalite
    }
    assert france["T"] == 2733


def test_salaires_par_age_sans_le_total():
    creuse = _lignes(vivre.SALAIRES_AGES, "23", 2024)
    # Le total tous âges vient du jeu par catégorie : il n'est pas lu deux fois.
    assert all(x.age_min is not None or x.age_max is not None for x in creuse)
    assert {(x.age_min, x.age_max) for x in creuse} == {
        (0, 24), (25, 39), (40, 49), (50, 54), (55, None),
    }  # fmt: skip
    assert {x.sexe for x in creuse} == {"T", "F", "H"}


def test_mesure_ou_dimension_inattendue_rejetee(tmp_path):
    contenu = json.loads((FIXTURES / "DS_FILOSOFI_CC.json").read_text(encoding="utf-8"))
    contenu["observations"][0]["dimensions"]["AGE"] = "Y18T29"
    chemin = tmp_path / "filosofi.json"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Dimensions inattendues"):
        list(vivre.REVENUS_FILOSOFI.lire(chemin, REFERENTIEL))
    chemin.write_text(json.dumps({"observations": contenu["observations"][:0]}), "utf-8")
    with pytest.raises(FichierIllisible, match="Aucune observation"):
        list(vivre.REVENUS_FILOSOFI.lire(chemin, REFERENTIEL))


def test_groupe_vivre():
    assert CONNECTEURS["vivre"] == JEUX


def test_import_et_api(urls_module):
    brut = config.charger().donnees_brutes
    with db.connexion("import") as conn:
        for jeu in JEUX:
            # Extraits réduits : la couverture départementale ne peut pas être complète
            # (contrôlée sur les fichiers entiers avant la PR : 97 et 101 départements).
            jeu = dataclasses.replace(jeu, controle_couverture=False)
            chemin = FIXTURES / jeu.nom_fichier
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            resultat = pipeline.importer(conn, jeu, fichier, brut, chemin_local=chemin)
            assert resultat.statut == "PUBLIE", resultat.message

    indicateurs = client.get("/api/v1/indicateurs", params={"rubrique": "VIVRE"}).json()
    par_code = {i["code"]: i for i in indicateurs}
    assert par_code["SALAIRE_NET_MOYEN"]["theme"] == "REVENUS"
    # Indicateurs des applis 1 et 2, affichés dans la rubrique sous son propre thème.
    assert par_code["NIVEAU_VIE_MEDIAN"]["rubrique"] == "VIVRE"
    assert par_code["NIVEAU_VIE_MEDIAN"]["theme"] == "REVENUS"
    assert par_code["NIVEAU_VIE_MEDIAN"]["angle"] is None
    assert par_code["PENSIONNES"]["theme"] == "RETRAITES"
    # Ils restent dans leur rubrique d'origine, sans doublon dans la liste complète.
    tous = client.get("/api/v1/indicateurs").json()
    assert [i["rubrique"] for i in tous if i["code"] == "NIVEAU_VIE_MEDIAN"] == ["BESOINS"]
    inegalites = client.get(
        "/api/v1/indicateurs", params={"rubrique": "VIVRE", "theme": "INEGALITES"}
    ).json()
    assert {"NIVEAU_VIE_D9", "TAUX_PAUVRETE"} <= {i["code"] for i in inegalites}

    fiche = client.get(
        "/api/v1/fiche", params={"niveau": "DEP", "code": "23", "rubrique": "VIVRE"}
    ).json()
    lignes = {ligne["indicateur"]["code"]: ligne for ligne in fiche["lignes"]}
    assert lignes["NIVEAU_VIE_D9"]["valeur"] == 37240
    assert lignes["NIVEAU_VIE_D9"]["france"]["code"] == "FM"
    assert lignes["SALAIRE_NET_MOYEN"]["annee"] == 2024
    assert lignes["SALAIRE_NET_MOYEN"]["france"] == {
        "code": "FR", "valeur": 2733, "provisoire": False,
    }  # fmt: skip
