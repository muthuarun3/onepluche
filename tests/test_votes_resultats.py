"""Appli « Que pensent et votent les Français ? », PR V2 : résultats des élections.

Extraits réels des deux fichiers Parquet de data.gouv.fr (« données des élections
agrégées ») : Creuse (23), Guadeloupe (971, codée ZA avant 2022), Nouvelle-Calédonie (988,
ZN), Français de l'étranger (ZZ) ; tours 2002 T1, 2022 T1 et T2, européennes 2024,
législatives 2024 T1 et municipales 2026 T1.
"""

from datetime import date
from decimal import Decimal

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import FIXTURES

from demographie import config, db
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs import elections as el
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

GENERAL = FIXTURES / "elections_general.parquet"
CANDIDATS = FIXTURES / "elections_candidats.parquet"
REFERENTIEL = Referentiel(identifiants={}, region_du_departement={})
MILLESIME = "2026-07-07T14:00:39"


def _extrait(classe):
    """Connecteur pour un extrait : les 101 départements ne sont pas tous là."""
    connecteur = classe()
    connecteur.couverture = False
    return connecteur


PARTICIPATION = _extrait(el.ParticipationElections)
VOIX = _extrait(el.VoixElections)


def _une(lignes, indicateur, niveau, code, jour, modalite=None):
    (ligne,) = [
        x
        for x in lignes
        if (x.indicateur, x.niveau, x.code, x.periode, x.modalite)
        == (indicateur, niveau, code, jour, modalite)
    ]
    return ligne


@pytest.mark.parametrize(
    ("code", "attendu"),
    [
        ("23", ("DEP", "23")),
        ("2A", ("DEP", "2A")),
        ("ZA", ("DEP", "971")),
        ("971", ("DEP", "971")),
        ("ZM", ("DEP", "976")),
        ("ZN", ("HORS_DEP", "COM")),
        ("988", ("HORS_DEP", "COM")),
        ("ZZ", ("HORS_DEP", "ZZ")),
    ],
)
def test_territoires(code, attendu):
    assert el.territoire(code) == attendu


def test_code_de_departement_inconnu():
    with pytest.raises(FichierIllisible, match="inconnu"):
        el.territoire("20")


def test_participation():
    lignes = list(PARTICIPATION.lire(GENERAL, REFERENTIEL))
    jour = date(2022, 4, 10)
    creuse = {
        i: _une(lignes, i, "DEP", "23", jour).valeur
        for i in ("INSCRITS", "ABSTENTIONS", "VOTANTS", "BLANCS", "NULS", "EXPRIMES")
    }
    assert creuse == {
        "INSCRITS": 90946,
        "ABSTENTIONS": 21967,
        "VOTANTS": 68979,
        "BLANCS": 1388,
        "NULS": 743,
        "EXPRIMES": 66848,
    }
    assert _une(lignes, "BLANCS_ET_NULS", "DEP", "23", jour).valeur == 1388 + 743
    ligne = _une(lignes, "INSCRITS", "HORS_DEP", "ZZ", jour)
    assert (ligne.periode_type, ligne.sexe, ligne.statut) == ("SCRUTIN", "T", "DEFINITIF")
    # France entière = départements + Français de l'étranger + collectivités d'outre-mer.
    assert _une(lignes, "INSCRITS", "FRANCE", "FR", jour).valeur == 2061488
    assert _une(lignes, "INSCRITS", "FRANCE", "FM", jour).valeur == 90946
    # Municipales : participation publiée.
    assert _une(lignes, "VOTANTS", "DEP", "971", date(2026, 3, 15)).valeur == 169951


def test_2002_blancs_avec_les_nuls_et_sans_france_entiere():
    lignes = [x for x in PARTICIPATION.lire(GENERAL, REFERENTIEL) if x.periode.year == 2002]
    assert {x.indicateur for x in lignes} == {
        "INSCRITS",
        "ABSTENTIONS",
        "VOTANTS",
        "BLANCS_ET_NULS",
        "EXPRIMES",
    }
    assert _une(lignes, "BLANCS_ET_NULS", "DEP", "23", date(2002, 4, 21)).valeur == 3729
    # Ni étranger ni collectivités dans le fichier en 2002 : pas de France entière.
    assert {(x.niveau, x.code) for x in lignes} == {
        ("DEP", "23"),
        ("DEP", "971"),
        ("FRANCE", "FM"),
    }


def test_choix_et_libelles():
    choix = {c.code: c for c in VOIX.choix(CANDIDATS)}
    macron = choix["PRES_2022_T1_P03"]
    assert (macron.libelle, macron.panneau, macron.sexe) == ("Emmanuel MACRON", 3, "H")
    assert choix["PRES_2022_T1_P05"].sexe == "F"
    # Prénoms en capitales en 2002 : remis en minuscules.
    assert choix["PRES_2002_T1_P06"].libelle == "Jean-Marie LE PEN"
    rn = choix["LEGI_2024_T1_RN"]
    assert (rn.nuance, rn.libelle, rn.panneau) == ("RN", "Rassemblement national", None)
    assert choix["EURO_2024_T1_L04"].libelle.startswith("LA FRANCE INSOUMISE")
    assert not any(c.scrutin.startswith("MUNI") for c in choix.values())


def test_voix():
    lignes = list(VOIX.lire(CANDIDATS, REFERENTIEL))
    jour = date(2022, 4, 24)
    macron = ("choix", "PRES_2022_T2_P01")
    assert _une(lignes, "VOIX", "DEP", "23", jour, macron).valeur == 30554
    assert _une(lignes, "VOIX", "FRANCE", "FR", jour, macron).valeur == 573452
    # Législatives : les candidats d'une même nuance additionnés.
    ug = ("choix", "LEGI_2024_T1_UG")
    assert _une(lignes, "VOIX", "DEP", "23", date(2024, 6, 30), ug).valeur == 14359
    # Somme des voix d'un tour présidentiel = exprimés.
    exprimes = _une(
        list(PARTICIPATION.lire(GENERAL, REFERENTIEL)), "EXPRIMES", "DEP", "23", jour
    ).valeur
    assert sum(x.valeur for x in lignes if (x.code, x.periode) == ("23", jour)) == exprimes


def _reecrire(tmp_path, source, nom, modifier):
    table = modifier(pq.read_table(source))
    chemin = tmp_path / nom
    pq.write_table(table, chemin)
    return chemin


def test_participation_incoherente(tmp_path):
    def gonfler(table):
        inscrits = table.column("inscrits").to_pylist()
        inscrits[0] += 1
        return table.set_column(
            table.column_names.index("inscrits"), "inscrits", pa.array(inscrits)
        )

    chemin = _reecrire(tmp_path, GENERAL, "general_results.parquet", gonfler)
    with pytest.raises(FichierIllisible, match="incohérents"):
        list(PARTICIPATION.lire(chemin, REFERENTIEL))


def test_nuance_inconnue(tmp_path):
    def inventer(table):
        nuances = ["XYZ" if n == "RN" else n for n in table.column("nuance").to_pylist()]
        return table.set_column(table.column_names.index("nuance"), "nuance", pa.array(nuances))

    chemin = _reecrire(tmp_path, CANDIDATS, "candidats_results.parquet", inventer)
    with pytest.raises(FichierIllisible, match="nuance inconnue"):
        VOIX.choix(chemin)


def test_fichier_complet_exige_tous_les_departements():
    with pytest.raises(FichierIllisible, match="départements absents|absent du fichier"):
        el.lire_participation(GENERAL, True)


def test_ressources_data_gouv(monkeypatch):
    ressources = [
        {
            "title": "Résultats généraux",
            "format": "parquet",
            "url": "https://exemple.fr/elections/general_results.parquet",
            "last_modified": "2026-07-07T14:00:39.123000+00:00",
        },
        {
            "title": "Résultats généraux",
            "format": "csv",
            "url": "https://exemple.fr/elections/general_results.csv",
        },
    ]
    monkeypatch.setattr(
        "demographie.imports.telechargement.lire_json", lambda url: {"resources": ressources}
    )
    (fichier,) = el.PARTICIPATION_ELECTIONS.fichiers()
    assert (fichier.nom, fichier.millesime) == ("general_results.parquet", MILLESIME)
    assert el.PARTICIPATION_ELECTIONS.accepte("general_results.parquet")
    assert CONNECTEURS["votes"] == (el.PARTICIPATION_ELECTIONS, el.VOIX_ELECTIONS)


# --- Import complet et vues de l'API ----------------------------------------------------


def _importer(connecteur, chemin, nom, chemin_local=True):
    fichier = Fichier(url=f"https://exemple.fr/elections/{nom}", nom=nom, millesime=MILLESIME)
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn,
            connecteur,
            fichier,
            config.charger().donnees_brutes,
            chemin_local=chemin if chemin_local else None,
        )


def test_import_et_vues(urls_module, monkeypatch):
    for connecteur, chemin, nom in (
        (PARTICIPATION, GENERAL, "general_results.parquet"),
        (VOIX, CANDIDATS, "candidats_results.parquet"),
    ):
        resultat = _importer(connecteur, chemin, nom)
        assert resultat.statut == "PUBLIE", (nom, resultat.message)

    with psycopg.connect(urls_module["lecture"]) as conn:
        participation = conn.execute(
            "SELECT scrutin, election, tour, inscrits, blancs, blancs_et_nuls, "
            "taux_abstention, taux_participation, part_blancs_votants "
            "FROM api.participation WHERE niveau = 'DEP' AND code = '23' ORDER BY jour"
        ).fetchall()
        resultat = conn.execute(
            "SELECT choix, libelle, panneau, voix, part_exprimes FROM api.resultat "
            "WHERE scrutin = 'PRES_2022_T2' AND niveau = 'FRANCE' AND code = 'FR' "
            "ORDER BY panneau"
        ).fetchall()
        nuance = conn.execute(
            "SELECT nuance, voix FROM api.resultat "
            "WHERE choix = 'LEGI_2024_T1_UG' AND niveau = 'DEP' AND code = '23'"
        ).fetchone()
    assert [p[0] for p in participation] == [
        "PRES_2002_T1",
        "PRES_2022_T1",
        "PRES_2022_T2",
        "EURO_2024_T1",
        "LEGI_2024_T1",
        "MUNI_2026_T1",
    ]
    assert participation[0][4:6] == (None, 3729)
    assert participation[1][1:] == (
        "PRESIDENTIELLE",
        1,
        90946,
        1388,
        2131,
        Decimal("24.15"),
        Decimal("75.85"),
        Decimal("2.01"),
    )
    assert resultat == [
        ("PRES_2022_T2_P01", "Emmanuel MACRON", 1, 573452, Decimal("72.09")),
        ("PRES_2022_T2_P02", "Marine LE PEN", 2, 222049, Decimal("27.91")),
    ]
    assert nuance == ("UG", 14359)

    # Même date de mise à jour sur data.gouv.fr : rien n'est téléchargé à nouveau.
    def interdit(*args, **kwargs):
        raise AssertionError("téléchargement inattendu")

    monkeypatch.setattr("demographie.imports.telechargement.telecharger", interdit)
    deja = _importer(PARTICIPATION, GENERAL, "general_results.parquet", chemin_local=False)
    assert deja.statut == "DEJA_IMPORTE", deja.message
