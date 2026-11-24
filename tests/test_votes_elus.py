"""Appli « Que pensent et votent les Français ? », PR V3 : portrait des élus.

Extraits réels du Répertoire national des élus (mise à jour du 20/11/2026), noms et
prénoms remplacés par « X » : Creuse (23), Guadeloupe (971), Alsace (conseillers
départementaux, code 6AE), Martinique (972, maires sans code de département), Polynésie
française (987) et Français de l'étranger (ZZ).
"""

from datetime import date
from decimal import Decimal

import psycopg
import pytest
from conftest import FIXTURES

from demographie import config, db
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs import elus as el
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

REFERENTIEL = Referentiel(identifiants={})
MOIS = date(2026, 11, 1)
FICHIERS = {m: FIXTURES / f"{m.prefixe}-2026-11-20.csv" for m in el.MANDATS}


def _extrait():
    connecteur = el.Elus()
    connecteur.couverture = False
    return connecteur


EXTRAIT = _extrait()


def _lignes(mandat_code):
    (mandat,) = [m for m in el.MANDATS if m.code == mandat_code]
    return list(EXTRAIT.lire(FICHIERS[mandat], REFERENTIEL))


def _une(lignes, indicateur, code, sexe="T", age=None, modalite=None):
    (ligne,) = [
        x
        for x in lignes
        if (x.indicateur, x.code, x.sexe, x.age_min, x.modalite)
        == (indicateur, code, sexe, age, modalite)
    ]
    return ligne


@pytest.mark.parametrize(
    ("ligne", "attendu"),
    [
        ({"Code du département": "23"}, ("DEP", "23")),
        ({"Code du département": "6AE", "Code du canton": "6812"}, ("DEP", "68")),
        ({"Code du département": "", "Code de la collectivité à statut particulier": "972"},
         ("DEP", "972")),
        ({"Code du département": "", "Code de la collectivité à statut particulier": "987"},
         ("HORS_DEP", "COM")),
        ({"Code du département": "", "Code de la commune": "49038"}, ("DEP", "49")),
        ({"Code du département": "ZZ"}, ("HORS_DEP", "ZZ")),
    ],
)  # fmt: skip
def test_territoires(ligne, attendu):
    assert el.territoire(ligne) == attendu


def test_age_a_la_date_du_fichier():
    jour = date(2026, 11, 20)
    assert el.age(date(1986, 11, 20), jour) == 40
    assert el.age(date(1986, 11, 21), jour) == 39


def test_maires():
    lignes = _lignes("MAIRE")
    creuse = _une(lignes, "ELUS_MAIRES", "23")
    assert (creuse.periode, creuse.periode_type, creuse.statut) == (MOIS, "MOIS", "DEFINITIF")
    total = creuse.valeur
    femmes = _une(lignes, "ELUS_MAIRES", "23", sexe="F").valeur
    hommes = _une(lignes, "ELUS_MAIRES", "23", sexe="H").valeur
    assert femmes + hommes == total
    tranches = [x.valeur for x in lignes if x.code == "23" and x.age_min is not None]
    assert sum(tranches) == total
    groupes = [x for x in lignes if x.code == "23" and x.modalite and x.modalite[0] == "pcs"]
    assert sum(x.valeur for x in groupes) == total
    assert {x.modalite[1] for x in groupes} <= set(el.GROUPES.values())
    mediane = _une(lignes, "AGE_MEDIAN_ELUS", "23", modalite=("mandat", "MAIRE"))
    assert 40 < mediane.valeur < 80
    # Martinique : maires sans code de département ; Polynésie : collectivité d'outre-mer.
    assert _une(lignes, "ELUS_MAIRES", "972").valeur == 33  # maires présents dans le fichier
    assert _une(lignes, "ELUS_MAIRES", "COM").valeur == 48
    assert (
        _une(lignes, "ELUS_MAIRES", "FR").valeur
        == len(FICHIERS[el.MANDATS[0]].read_text(encoding="utf-8").splitlines()) - 1
    )
    # Seuls des comptes : aucun texte venu du fichier.
    assert all(isinstance(x.valeur, int | Decimal) for x in lignes)


def test_conseillers_departementaux_alsace_repartie():
    lignes = _lignes("CONSEILLER_DEP")
    bas_rhin = _une(lignes, "ELUS_CONSEILLERS_DEP", "67").valeur
    haut_rhin = _une(lignes, "ELUS_CONSEILLERS_DEP", "68").valeur
    assert bas_rhin + haut_rhin == 80
    assert not [x for x in lignes if x.code == "6AE"]


def test_deputes_de_l_etranger():
    lignes = _lignes("DEPUTE")
    assert _une(lignes, "ELUS_DEPUTES", "ZZ").valeur == 11
    fm = _une(lignes, "ELUS_DEPUTES", "FM").valeur
    assert fm == _une(lignes, "ELUS_DEPUTES", "23").valeur


def test_departement_manquant(tmp_path):
    chemin = tmp_path / FICHIERS[el.MANDATS[2]].name
    chemin.write_text(FICHIERS[el.MANDATS[2]].read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(FichierIllisible, match="départements absents"):
        list(el.ELUS.lire(chemin, REFERENTIEL))


def test_categorie_illisible(tmp_path):
    source = FICHIERS[el.MANDATS[3]]
    texte = source.read_text(encoding="utf-8").replace(";33;Cadre", ";;Cadre", 1)
    chemin = tmp_path / source.name
    chemin.write_text(texte, encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Catégorie illisible"):
        list(EXTRAIT.lire(chemin, REFERENTIEL))


def test_ressources_data_gouv(monkeypatch):
    ressources = [
        {
            "title": m.titre,
            "url": f"https://static.data.gouv.fr/resources/rne/20261120-104746/{m.prefixe}.csv",
            "last_modified": "2026-11-20T10:47:46.123000+00:00",
        }
        for m in el.MANDATS
    ] + [{"title": "elus-conseillers-municipaux-cm.csv", "url": "https://x/cm.csv"}]
    monkeypatch.setattr(
        "demographie.imports.telechargement.lire_json", lambda url: {"resources": ressources}
    )
    fichiers = el.ELUS.fichiers()
    assert [f.nom for f in fichiers] == [p.name for p in FICHIERS.values()]
    assert {f.millesime for f in fichiers} == {"2026-11-20"}
    assert all(el.ELUS.accepte(f.nom) for f in fichiers)
    assert not el.ELUS.accepte("elus-conseillers-municipaux-2026-11-20.csv")
    assert CONNECTEURS["votes"][-1] is el.ELUS


def test_import_et_vue(urls_module):
    for chemin in FICHIERS.values():
        fichier = Fichier(url=f"https://exemple.fr/{chemin.name}", nom=chemin.name)
        with db.connexion("import") as conn:
            resultat = pipeline.importer(
                conn, EXTRAIT, fichier, config.charger().donnees_brutes, chemin_local=chemin
            )
        assert resultat.statut == "PUBLIE", (chemin.name, resultat.message)

    with psycopg.connect(urls_module["lecture"]) as conn:
        lignes = conn.execute(
            "SELECT mandat, elus, femmes, moins_de_40_ans, age_median, part_femmes, "
            "part_moins_de_40_ans FROM api.elus WHERE niveau = 'DEP' AND code = '23' "
            "ORDER BY mandat"
        ).fetchall()
        groupes = conn.execute(
            "SELECT sum(valeur) FROM api.ventilation WHERE indicateur = 'ELUS_MAIRES' "
            "AND niveau = 'DEP' AND code = '23' AND dimension = 'pcs'"
        ).fetchone()[0]
    assert [x[0] for x in lignes] == ["CONSEILLER_DEP", "DEPUTE", "MAIRE", "SENATEUR"]
    maires = dict(zip(["mandat", "elus", "femmes", "jeunes", "mediane", "pf", "pj"],
                      lignes[2], strict=True))  # fmt: skip
    assert maires["pf"] == round(Decimal(100) * maires["femmes"] / maires["elus"], 1)
    assert maires["mediane"] is not None
    assert groupes == maires["elus"]
