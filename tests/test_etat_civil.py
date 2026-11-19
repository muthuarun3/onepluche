"""Naissances et décès (jeux Melodi de l'INSEE, extraits réels 2023-2025)."""

import zipfile
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs.melodi import DECES, NAISSANCES
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

ZIP_NAISSANCES = FIXTURES / "DS_NAISSANCES_FECONDITE_SERIES.zip"
ZIP_DECES = FIXTURES / "DS_DECES_MORTALITE_SERIES.zip"
REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement={"75": "11", "92": "11", "976": "06", "971": "01", "23": "75"},
)
client = TestClient(app)


def _valeurs(lignes, indicateur, niveau, code, annee, sexe="T"):
    return [
        ligne
        for ligne in lignes
        if (ligne.indicateur, ligne.niveau, ligne.code, ligne.periode, ligne.sexe)
        == (indicateur, niveau, code, date(annee, 1, 1), sexe)
    ]


@pytest.fixture(scope="module")
def naissances():
    return list(NAISSANCES.lire(ZIP_NAISSANCES, REFERENTIEL))


@pytest.fixture(scope="module")
def deces():
    return list(DECES.lire(ZIP_DECES, REFERENTIEL))


def test_naissances(naissances):
    (france,) = _valeurs(naissances, "NAISSANCES", "FRANCE", "FR", 2025)
    assert france.valeur == 642_905 and france.periode_type == "ANNEE"
    (icf,) = _valeurs(naissances, "ICF", "FRANCE", "FR", 2025)
    assert icf.valeur == Decimal("1.56") and icf.statut == "PROVISOIRE"
    assert {ligne.indicateur for ligne in naissances} == {"NAISSANCES", "TAUX_NATALITE", "ICF"}
    # Agrégats hors référentiel ignorés (France métropolitaine hors Île-de-France, « DOM »).
    assert not {"FM_X_R11", "DOM", "F"} & {ligne.code for ligne in naissances}


def test_region_d_outre_mer_reprend_son_departement(naissances):
    (mayotte,) = _valeurs(naissances, "NAISSANCES", "DEP", "976", 2024)
    (region,) = _valeurs(naissances, "NAISSANCES", "REG", "06", 2024)
    assert region.valeur == mayotte.valeur
    # L'Île-de-France compte plusieurs départements : pas de duplication.
    assert len(_valeurs(naissances, "NAISSANCES", "REG", "11", 2024)) == 1


def test_esperance_de_vie_par_sexe(deces):
    assert _valeurs(deces, "ESPERANCE_VIE", "FRANCE", "FR", 2025, "T") == []
    (femmes,) = _valeurs(deces, "ESPERANCE_VIE", "FRANCE", "FR", 2025, "F")
    (hommes,) = _valeurs(deces, "ESPERANCE_VIE", "FRANCE", "FR", 2025, "H")
    assert femmes.valeur > hommes.valeur > 70


def _archive_modifiee(tmp_path, source, transformer):
    cible = tmp_path / source.name
    with zipfile.ZipFile(source) as entree, zipfile.ZipFile(cible, "w") as sortie:
        for nom in entree.namelist():
            contenu = entree.read(nom).decode("utf-8")
            sortie.writestr(nom, transformer(nom, contenu))
    return cible


def test_colonne_absente_refusee(tmp_path):
    chemin = _archive_modifiee(
        tmp_path,
        ZIP_NAISSANCES,
        lambda nom, c: c.replace('"OBS_STATUS";', '"STATUT";', 1) if "_data" in nom else c,
    )
    with pytest.raises(FichierIllisible, match="OBS_STATUS"):
        list(NAISSANCES.lire(chemin, REFERENTIEL))


def _importer(connecteur, chemin):
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_somme_des_departements_controlee(urls_module, tmp_path):
    # Naissances de Paris doublées en 2024 : la France ne vaut plus la somme.
    def doubler(nom, contenu):
        if "_data" not in nom:
            return contenu
        lignes = contenu.splitlines(keepends=True)
        entete = [c.strip('"') for c in lignes[0].strip().split(";")]
        for i, ligne in enumerate(lignes[1:], start=1):
            champs = dict(
                zip(entete, [c.strip('"') for c in ligne.strip().split(";")], strict=True)
            )
            cle = (champs["GEO"], champs["GEO_OBJECT"], champs["EC_MEASURE"])
            if cle == ("75", "DEP", "LVB_PLACE_RES") and champs["TIME_PERIOD"] == "2024":
                lignes[i] = ligne.replace(champs["OBS_VALUE"], str(int(champs["OBS_VALUE"]) * 2))
        return "".join(lignes)

    resultat = _importer(NAISSANCES, _archive_modifiee(tmp_path, ZIP_NAISSANCES, doubler))
    assert resultat.statut == "REJETE"
    assert "NAISSANCES FR 2024" in resultat.message


def test_import_et_api(urls_module):
    assert _importer(NAISSANCES, ZIP_NAISSANCES).statut == "PUBLIE"
    assert _importer(DECES, ZIP_DECES).statut == "PUBLIE"

    def serie(indicateur, **params):
        parametres = {"indicateur": indicateur, "niveau": "FRANCE", "code": "FR", **params}
        return client.get("/api/v1/series", params=parametres).json()["valeurs"]

    solde = {v["annee"]: v["valeur"] for v in serie("SOLDE_NATUREL")}
    naissances = {v["annee"]: v["valeur"] for v in serie("NAISSANCES")}
    deces = {v["annee"]: v["valeur"] for v in serie("DECES")}
    assert solde == {a: naissances[a] - deces[a] for a in (2023, 2024, 2025)}
    assert solde[2025] < 0  # premier solde naturel négatif depuis 1945
    assert serie("ESPERANCE_VIE") == []
    femmes = serie("ESPERANCE_VIE", sexe="F")
    assert [v["annee"] for v in femmes] == [2023, 2024, 2025]
    indicateurs = {i["code"] for i in client.get("/api/v1/indicateurs").json()}
    assert {"NAISSANCES", "DECES", "SOLDE_NATUREL", "ICF", "ESPERANCE_VIE"} <= indicateurs
