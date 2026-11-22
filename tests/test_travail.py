"""Appli travail, PR T1 : séries de la BDM de l'INSEE (extraits réels 2023-2026).

Gironde, Paris, Guadeloupe et Mayotte, leurs régions et la France ; fabriqués par
tests/fixtures/reduire_travail.py.
"""

import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs.travail import (
    CHOMAGE_ANNUEL,
    CREATIONS,
    DEFAILLANCES,
    EMPLOI_SALARIE,
    EMPLOI_TOTAL,
)
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={"33": "75", "75": "11", "971": "01", "976": "06"},
)
JEUX = (CHOMAGE_ANNUEL, EMPLOI_SALARIE, EMPLOI_TOTAL, CREATIONS, DEFAILLANCES)
client = TestClient(app)


def _lire(jeu):
    return list(jeu.lire(FIXTURES / jeu.nom_fichier, REFERENTIEL))


def _une(lignes, indicateur, code, periode, sexe="T", age=None, modalite=None):
    (ligne,) = [
        x
        for x in lignes
        if (x.indicateur, x.code, x.periode, x.sexe, x.age_min, x.modalite)
        == (indicateur, code, periode, sexe, age, modalite)
    ]
    return ligne


def test_chomage_par_sexe_et_age():
    lignes = _lire(CHOMAGE_ANNUEL)
    an = date(2025, 1, 1)
    assert _une(lignes, "TAUX_CHOMAGE_ANNUEL", "33", an).valeur == Decimal("7.3")
    jeunes = _une(lignes, "TAUX_CHOMAGE_ANNUEL", "33", an, age=15)
    assert (jeunes.valeur, jeunes.age_max) == (Decimal("19.0"), 24)
    assert _une(lignes, "TAUX_CHOMAGE_ANNUEL", "33", an, age=50).age_max is None
    assert _une(lignes, "TAUX_CHOMAGE_ANNUEL", "33", an, sexe="F").valeur == Decimal("7.2")
    # Outre-mer et France : taux de l'enquête Emploi, dans le même indicateur.
    assert _une(lignes, "TAUX_CHOMAGE_ANNUEL", "971", an).valeur == Decimal("16.6")
    assert _une(lignes, "TAUX_CHOMAGE_ANNUEL", "FR", an).valeur == Decimal("7.7")
    codes = {(x.niveau, x.code) for x in lignes}
    assert ("REG", "01") in codes and ("DEP", "976") not in codes


def test_emploi_salarie_et_interim():
    lignes = _lire(EMPLOI_SALARIE)
    t2 = date(2026, 4, 1)
    total = _une(lignes, "EMPLOI_SALARIE", "33", t2)
    assert (total.valeur, total.statut, total.periode_type) == (702900, "PROVISOIRE", "TRIMESTRE")
    interim = _une(lignes, "EMPLOI_SALARIE", "33", t2, modalite=("secteur", "INTERIM"))
    assert interim.valeur == 16289
    assert _une(lignes, "PART_INTERIM", "33", t2).valeur == Decimal("2.3")
    assert _une(lignes, "EMPLOI_SALARIE", "FR", t2).valeur == 27021067


def test_emploi_total_et_independants():
    lignes = _lire(EMPLOI_TOTAL)
    fin_2024 = date(2024, 1, 1)
    assert _une(lignes, "EMPLOI_TOTAL", "33", fin_2024).valeur == 809244
    independants = ("statut_emploi", "NON_SALARIE")
    assert _une(lignes, "EMPLOI_TOTAL", "33", fin_2024, modalite=independants).valeur == 105650
    assert _une(lignes, "PART_INDEPENDANTS", "33", fin_2024).valeur == Decimal("13.1")


def test_creations_et_defaillances():
    creations = _lire(CREATIONS)
    octobre = date(2026, 10, 1)
    assert _une(creations, "CREATIONS_ENTREPRISES", "33", octobre).valeur == 4122
    micro = ("type_entreprise", "MICRO")
    assert _une(creations, "CREATIONS_ENTREPRISES", "33", octobre, modalite=micro).valeur == 3073
    assert _une(creations, "CREATIONS_ENTREPRISES", "976", octobre).periode_type == "MOIS"
    assert not [x for x in creations if x.niveau == "REG"]  # pas de régions publiées
    defaillances = _lire(DEFAILLANCES)
    assert _une(defaillances, "DEFAILLANCES_ENTREPRISES", "33", date(2026, 4, 1)).valeur == 653


def test_somme_des_secteurs_controlee(tmp_path):
    texte = (FIXTURES / EMPLOI_SALARIE.nom_fichier).read_text(encoding="utf-8")
    # La construction de la Gironde au 2e trimestre 2026 passe de 39 117 à 139 117.
    chemin = tmp_path / EMPLOI_SALARIE.nom_fichier
    chemin.write_text(texte.replace('OBS_VALUE="39117"', 'OBS_VALUE="139117"'), "utf-8")
    with pytest.raises(FichierIllisible, match="somme des parties"):
        list(EMPLOI_SALARIE.lire(chemin, REFERENTIEL))


def test_serie_inattendue_refusee(tmp_path):
    texte = (FIXTURES / DEFAILLANCES.nom_fichier).read_text(encoding="utf-8")
    chemin = tmp_path / DEFAILLANCES.nom_fichier
    chemin.write_text(texte.replace('ACTIVITE_CREAT_ENT="ENS"', 'ACTIVITE_CREAT_ENT="AZ"', 1))
    with pytest.raises(FichierIllisible, match="Série inattendue"):
        list(DEFAILLANCES.lire(chemin, REFERENTIEL))


def test_cle_filtree_dans_l_url():
    assert EMPLOI_TOTAL.fichiers()[0].url.endswith(
        "/TCRED-EMPLOI-31-DECEMBRE-BASE-2018/A.EMPLOI_31_DECEMBRE.TOT.VALEUR_ABSOLUE.SAL+NSAL+TOT....."
    )
    assert CONNECTEURS["travail"][: len(JEUX)] == JEUX


def test_import_et_api(urls_module):
    for jeu in JEUX:
        # Extraits de 4 départements : la France ne peut pas égaler leur somme.
        reduit = dataclasses.replace(jeu, controle_couverture=False, tolerance_sommes=1.0)
        chemin = FIXTURES / jeu.nom_fichier
        fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
        with db.connexion("import") as conn:
            resultat = pipeline.importer(
                conn, reduit, fichier, config.charger().donnees_brutes, chemin_local=chemin
            )
        assert resultat.statut == "PUBLIE", (jeu.nom_fichier, resultat.message)

    serie = client.get(
        "/api/v1/series",
        params={"indicateur": "PART_INTERIM", "niveau": "DEP", "code": "33", "debut": 2026},
    ).json()
    assert serie["valeurs"][-1]["valeur"] == 2.3
    assert "agence" in serie["indicateur"]["avertissement"]
    indicateurs = client.get(
        "/api/v1/indicateurs", params={"rubrique": "TRAVAIL", "theme": "EMPLOI"}
    ).json()
    codes = {i["code"] for i in indicateurs}
    assert {"EMPLOI_SALARIE", "PART_INTERIM", "EMPLOI_TOTAL", "PART_INDEPENDANTS"} <= codes
