"""Appli 3 « Que pensent et votent les Français ? », PR V1 : fondations de la rubrique."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from demographie.app import app

client = TestClient(app)


def test_rubrique_et_themes(base_test):
    with psycopg.connect(base_test["lecture"]) as conn:
        lignes = conn.execute(
            "SELECT rubrique_libelle, rubrique_chemin, rubrique_ordre, theme FROM api.theme "
            "WHERE rubrique = 'VOTES' ORDER BY theme_ordre"
        ).fetchall()
    assert [ligne[3] for ligne in lignes] == ["PARTICIPATION", "RESULTATS", "ELUS"]
    assert lignes[0][:3] == ("Que pensent et votent les Français ?", "/votes", 4)


def test_vingt_scrutins(base_test):
    with psycopg.connect(base_test["lecture"]) as conn:
        scrutins = conn.execute(
            "SELECT code, election, annee, tour, jour, type_choix FROM api.scrutin ORDER BY jour"
        ).fetchall()
    assert len(scrutins) == 20
    comptes: dict[str, int] = {}
    for code, election, annee, tour, jour, _ in scrutins:
        comptes[election] = comptes.get(election, 0) + 1
        assert code == f"{election[:4]}_{annee}_T{tour}"
        assert jour.year == annee
    assert comptes == {"PRESIDENTIELLE": 10, "LEGISLATIVES": 4, "EUROPEENNES": 2, "MUNICIPALES": 4}
    # Les municipales : participation seulement.
    assert {s[5] for s in scrutins if s[1] == "MUNICIPALES"} == {None}
    assert str(next(s[4] for s in scrutins if s[0] == "PRES_2022_T1")) == "2022-04-10"


def test_territoires_hors_departement(base_test):
    with psycopg.connect(base_test["lecture"]) as conn:
        hors = conn.execute(
            "SELECT code, parent_niveau, parent_code FROM api.territoire "
            "WHERE niveau = 'HORS_DEP' ORDER BY code"
        ).fetchall()
    assert hors == [("COM", "FRANCE", "FR"), ("ZZ", "FRANCE", "FR")]


def test_hors_departement_absents_des_enfants_de_la_france(urls_db):
    from demographie import db
    from demographie.donnees import territoires

    with db.connexion("lecture") as conn:
        enfants = territoires.enfants(conn, "FRANCE", "FR")
    assert enfants
    assert {e["niveau"] for e in enfants} <= {"FRANCE", "REG"}


def test_api_territoires_hors_departement(urls_db):
    reponse = client.get("/api/v1/territoires", params={"niveau": "HORS_DEP"})
    assert reponse.status_code == 200
    assert [t["code"] for t in reponse.json()] == ["COM", "ZZ"]


def test_type_de_periode_scrutin(base_test):
    with psycopg.connect(base_test["proprietaire"]) as conn:
        definition = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'observation_periode_type_check'"
        ).fetchone()[0]
    assert "SCRUTIN" in definition


# --- Ajout des choix par le rôle d'import ------------------------------------------------


def _ajouter(conn, scrutin: str, code: str, **autres) -> int:
    valeurs = {"panneau": None, "nuance": None, "nuance_libelle": None, "sexe": None} | autres
    return conn.execute(
        "SELECT ref.ajouter_choix(%s, %s, %s, %s::smallint, %s, %s, %s)",
        (
            scrutin,
            code,
            autres.get("libelle", code),
            valeurs["panneau"],
            valeurs["nuance"],
            valeurs["nuance_libelle"],
            valeurs["sexe"],
        ),
    ).fetchone()[0]


def test_ajouter_choix_par_le_role_d_import(base_test):
    with psycopg.connect(base_test["import"]) as conn:
        premier = _ajouter(conn, "PRES_2022_T2", "PRES_2022_T2_P01", panneau=1, sexe="H")
        # Rejouer l'import ne crée pas de doublon.
        assert _ajouter(conn, "PRES_2022_T2", "PRES_2022_T2_P01", panneau=1, sexe="H") == premier
        _ajouter(
            conn,
            "LEGI_2024_T1",
            "LEGI_2024_T1_SOC",
            nuance="SOC",
            nuance_libelle="Parti socialiste",
        )
        conn.commit()
    with psycopg.connect(base_test["lecture"]) as conn:
        lignes = conn.execute(
            "SELECT scrutin, code, libelle, panneau, nuance, sexe FROM api.choix_scrutin "
            "ORDER BY code"
        ).fetchall()
    assert lignes == [
        ("LEGI_2024_T1", "LEGI_2024_T1_SOC", "LEGI_2024_T1_SOC", None, "SOC", None),
        ("PRES_2022_T2", "PRES_2022_T2_P01", "PRES_2022_T2_P01", 1, None, "H"),
    ]
    # Base partagée par la session : on retire ces choix de test.
    with psycopg.connect(base_test["proprietaire"]) as conn:
        conn.execute("DELETE FROM ref.choix_scrutin")
        conn.execute("DELETE FROM ref.modalite WHERE dimension = 'choix'")


@pytest.mark.parametrize(
    ("scrutin", "code", "erreur"),
    [
        ("PRES_2027_T1", "PRES_2027_T1_P01", psycopg.errors.ForeignKeyViolation),
        ("PRES_2022_T1", "PRES_2017_T1_P01", psycopg.errors.CheckViolation),
    ],
)
def test_ajouter_choix_refuse(base_test, scrutin, code, erreur):
    with psycopg.connect(base_test["import"]) as conn, pytest.raises(erreur):
        _ajouter(conn, scrutin, code, panneau=1)


def test_role_d_import_sans_ecriture_directe_des_modalites(base_test):
    with (
        psycopg.connect(base_test["import"]) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(
            "INSERT INTO ref.modalite (dimension, code, libelle) VALUES ('choix', 'X', 'X')"
        )
