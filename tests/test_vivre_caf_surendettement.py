"""Appli 3, phase B : allocataires des CAF, surendettement (Banque de France), calculs."""

import dataclasses
import zipfile
from datetime import date
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS, EstimationsDepartements, caf
from demographie.imports.connecteurs.surendettement import Surendettement
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

client = TestClient(app)

# Nouvelle-Aquitaine : départements des extraits (CAF, Banque de France, estimations).
NOUVELLE_AQUITAINE = {
    "16": "Charente",
    "17": "Charente-Maritime",
    "19": "Corrèze",
    "23": "Creuse",
    "24": "Dordogne",
    "33": "Gironde",
    "40": "Landes",
    "47": "Lot-et-Garonne",
    "64": "Pyrénées-Atlantiques",
    "79": "Deux-Sèvres",
    "86": "Vienne",
    "87": "Haute-Vienne",
}
REFERENTIEL = Referentiel(
    identifiants={},
    region_du_departement=dict.fromkeys(NOUVELLE_AQUITAINE, "75"),
    libelles_departements=NOUVELLE_AQUITAINE,
)
ARCHIVE = FIXTURES / "SUREN-2025.zip"


def _valeurs(lignes, indicateur, niveau="DEP"):
    return {
        (x.code, x.periode.year, x.modalite[1] if x.modalite else None): x.valeur
        for x in lignes
        if x.indicateur == indicateur and x.niveau == niveau
    }


def test_rsa_en_decembre():
    lignes = list(caf.RSA.lire(FIXTURES / caf.RSA.nom_fichier, REFERENTIEL))
    rsa = _valeurs(lignes, "FOYERS_RSA")
    # Les codes hors référentiel (99, 978, XX) sont ignorés.
    assert {code for code, _, _ in rsa} == set(NOUVELLE_AQUITAINE)
    assert {annee for _, annee, _ in rsa} == {2023, 2024, 2025}
    assert {x.periode for x in lignes} == {date(a, 12, 1) for a in (2023, 2024, 2025)}
    assert {x.periode_type for x in lignes} == {"MOIS"}
    # La France est la somme des départements lus.
    france = _valeurs(lignes, "FOYERS_RSA", "FRANCE")
    assert france[("FR", 2024, None)] == sum(v for (_, a, _), v in rsa.items() if a == 2024)


def test_aides_au_logement_par_type():
    jeu = caf.AIDES_LOGEMENT
    lignes = list(jeu.lire(FIXTURES / jeu.nom_fichier, REFERENTIEL))
    foyers = _valeurs(lignes, "FOYERS_AIDES_LOGEMENT")
    gironde = {m: v for (code, a, m), v in foyers.items() if code == "33" and a == 2025}
    assert set(gironde) == {None, "LOCATION", "ACCESSION", "FOYER"}
    # Le total compte aussi les logements de type inconnu.
    assert gironde[None] >= gironde["LOCATION"] + gironde["ACCESSION"] + gironde["FOYER"]
    assert gironde["LOCATION"] > gironde["FOYER"] > 0
    montants = _valeurs(lignes, "MONTANT_AIDES_LOGEMENT")
    # Aide moyenne par foyer : entre 100 et 400 euros par mois.
    assert 100 < montants[("33", 2025, None)] / gironde[None] < 400
    assert {x.modalite[0] for x in lignes if x.modalite} == {"logement_aide"}


def test_colonne_absente(tmp_path):
    chemin = tmp_path / "caf.csv"
    chemin.write_text("dtreffre;numdep\n2024-12;33\n", encoding="utf-8")
    with pytest.raises(FichierIllisible, match="indfoy_rsa"):
        list(caf.RSA.lire(chemin, REFERENTIEL))


def test_liens_des_classeurs_regionaux():
    page = (
        '<a href="/system/files/2026-02/SUREN-2025_Bretagne.xlsx">Bretagne</a>'
        '<a href="/system/files/2026-02/SUREN-2025_Nouvelle-Aquitaine_0.xlsx">NAQ</a>'
        '<a href="/system/files/2026-02/SUREN-2025_Bretagne.xlsx">doublon</a>'
        '<a href="/system/files/2026-02/SUREN-2025_DOM.xlsx">Outre-mer</a>'
        '<a href="/system/files/2026-02/SUREN-2025_cahier_regional.xlsx">Cahier</a>'
        '<a href="/system/files/2026-02/SUREN-2025_DETTES_National.xlsx">France</a>'
        '<a href="/system/files/2026-02/SUREN-2025_COMPARAISONS-REGIONALES.xlsx">Régions</a>'
        '<a href="/system/files/2026-02/SUREN-2024_Bretagne.xlsx">Année d\'avant</a>'
    )
    assert Surendettement.liens(page, 2025) == [
        "https://www.banque-france.fr/system/files/2026-02/SUREN-2025_Bretagne.xlsx",
        "https://www.banque-france.fr/system/files/2026-02/SUREN-2025_Nouvelle-Aquitaine_0.xlsx",
    ]


def test_pages_reelles_2024_et_2025():
    """Noms des classeurs relevés sur les pages de 2024 et 2025 : treize régions."""
    regions = [
        "Auvergne-Rhone-Alpes", "Bourgogne-Franche-Comte", "Bretagne", "Centre-Val%20de%20Loire",
        "Corse", "Grand_Est", "Hauts-de-France", "Ile-de-France", "Normandie",
        "Nouvelle-Aquitaine", "Occitanie", "Pays_de_la_Loire", "Provence-Alpes-Cote_d-Azur",
    ]  # fmt: skip
    autres = ["DOM", "National", "COMPARAISONS-REGIONALES"]
    page = "".join(
        f'<a href="/system/files/2025-03/SUREN-2024_DETTES_{nom}.xlsx">x</a>'
        for nom in regions + autres
    )
    assert len(Surendettement.liens(page, 2024)) == 13


def test_surendettement_par_departement():
    lignes = list(Surendettement().lire(ARCHIVE, REFERENTIEL))
    dossiers = _valeurs(lignes, "DOSSIERS_SURENDETTEMENT")
    assert dossiers[("23", 2025, None)] == 319
    assert dossiers[("33", 2025, None)] == 3137
    assert len(dossiers) == 12
    # France métropolitaine : somme des départements (ici la seule Nouvelle-Aquitaine).
    (fm,) = _valeurs(lignes, "DOSSIERS_SURENDETTEMENT", "FRANCE").values()
    assert fm == sum(dossiers.values()) == 11561
    creuse = {m: v for (c, _, m), v in _valeurs(lignes, "ENDETTEMENT_MEDIAN").items() if c == "23"}
    assert creuse == {
        None: 16556,
        "HORS_IMMOBILIER": 15618,
        "IMMOBILIER": 61289,
        "CONSOMMATION": 14543,
        "CHARGES_COURANTES": 3204,
    }
    assert {x.periode for x in lignes} == {date(2025, 1, 1)}
    assert all(isinstance(x.valeur, Decimal) for x in lignes)


def test_onglet_departemental_manquant():
    referentiel = dataclasses.replace(
        REFERENTIEL,
        region_du_departement={**REFERENTIEL.region_du_departement, "35": "53"},
        libelles_departements={**NOUVELLE_AQUITAINE, "35": "Ille-et-Vilaine"},
    )
    with pytest.raises(FichierIllisible, match="35"):
        list(Surendettement().lire(ARCHIVE, referentiel))


def test_archive_inattendue(tmp_path):
    chemin = tmp_path / "SUREN-2025.zip"
    with zipfile.ZipFile(chemin, "w") as archive:
        archive.writestr("notes.txt", "rien")
    with pytest.raises(FichierIllisible, match="inattendu"):
        list(Surendettement().lire(chemin, REFERENTIEL))


def test_groupes():
    assert CONNECTEURS["vivre"][-2:] == (caf.RSA, caf.AIDES_LOGEMENT)
    (seul,) = CONNECTEURS["surendettement"]
    assert seul.accepte("SUREN-2025.zip") and not seul.accepte("SUREN-2025_Bretagne.xlsx")


class _SurendettementNouvelleAquitaine(Surendettement):
    """L'extrait ne couvre qu'une région : on lit avec ses seuls départements."""

    controle_couverture = False

    def lire(self, chemin, referentiel):
        return super().lire(chemin, dataclasses.replace(referentiel, **_restreint(referentiel)))


def _restreint(referentiel):
    return {
        "libelles_departements": {
            k: v for k, v in referentiel.libelles_departements.items() if k in NOUVELLE_AQUITAINE
        }
    }


def _importer(connecteur, nom):
    chemin = FIXTURES / nom
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn, connecteur, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )


def test_import_et_calculs(urls_module):
    etapes = [
        (EstimationsDepartements(), "estim-pop-dep-sexe-aq-1975-2026.xlsx"),
        (dataclasses.replace(caf.RSA, controle_couverture=False), caf.RSA.nom_fichier),
        (
            dataclasses.replace(caf.AIDES_LOGEMENT, controle_couverture=False),
            caf.AIDES_LOGEMENT.nom_fichier,
        ),
        (_SurendettementNouvelleAquitaine(), ARCHIVE.name),
    ]
    for connecteur, nom in etapes:
        resultat = _importer(connecteur, nom)
        assert resultat.statut == "PUBLIE", (nom, resultat.message)

    def serie(indicateur, code="33"):
        reponse = client.get(
            "/api/v1/series", params={"indicateur": indicateur, "niveau": "DEP", "code": code}
        ).json()
        return {v["annee"]: v["valeur"] for v in reponse["valeurs"]}

    with db.connexion("import") as conn:
        population = conn.execute(
            "SELECT s.population FROM stat.structure_age s "
            "JOIN ref.territoire t USING (territoire_id) "
            "WHERE t.niveau = 'DEP' AND t.code = '33' AND s.periode = '2025-01-01'"
        ).fetchone()["population"]
        rsa_2024 = conn.execute(
            "SELECT o.valeur FROM stat.observation o "
            "JOIN ref.indicateur i USING (indicateur_id) "
            "JOIN ref.territoire t USING (territoire_id) "
            "WHERE i.code = 'FOYERS_RSA' AND t.niveau = 'DEP' AND t.code = '33' "
            "AND o.periode = '2024-12-01' AND o.modalite_id IS NULL"
        ).fetchone()["valeur"]

    # RSA de décembre 2024 rapporté à la population du 1er janvier 2025.
    rsa = serie("FOYERS_RSA_POUR_1000")
    assert rsa[2024] == pytest.approx(float(round(1000 * rsa_2024 / population, 1)))
    assert 10 < rsa[2024] < 60
    surendettement = serie("SURENDETTEMENT_POUR_100000")
    assert surendettement[2025] == pytest.approx(round(100000 * 3137 / float(population)))
    aide = serie("AIDE_LOGEMENT_MOYENNE")
    assert set(aide) == {2023, 2024, 2025} and all(100 < v < 400 for v in aide.values())
    assert serie("DOSSIERS_SURENDETTEMENT", "23") == {2025: 319}

    vivre = client.get("/api/v1/indicateurs", params={"rubrique": "VIVRE"}).json()
    calculs = {i["code"]: i for i in vivre if i["code"].endswith(("_POUR_1000", "_100000"))}
    assert set(calculs) == {"FOYERS_RSA_POUR_1000", "SURENDETTEMENT_POUR_100000"}
    assert all(i["formule"].startswith("calcul On épluche") for i in calculs.values())
