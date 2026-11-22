"""Rubriques, thèmes et unités en tables de référence (migration 026).

Une nouvelle application ajoute ses lignes dans ref.rubrique, ref.theme et ref.unite, sans
réécrire de contrainte. Ces tests le font dans une base propre au module.
"""

import psycopg
import pytest
from fastapi.testclient import TestClient

from demographie.app import app

client = TestClient(app)

_INSERER = """INSERT INTO ref.indicateur
                (code, libelle, definition, unite, nature, source_id, rubrique, theme, angle)
              SELECT %s, 'x', 'x', %s, 'taux', source_id, %s, %s, %s
              FROM ref.source WHERE code = 'INSEE_RP'"""


def test_rubriques_existantes(base_test):
    with psycopg.connect(base_test["proprietaire"]) as conn:
        rubriques = conn.execute(
            "SELECT code, chemin, theme_obligatoire FROM ref.rubrique ORDER BY ordre"
        ).fetchall()
        assert rubriques == [("QUI", "/francais", False), ("BESOINS", "/besoins", True)]
        # Chaque indicateur déjà en base a sa rubrique, son thème et son unité en référence.
        orphelins = conn.execute(
            """SELECT count(*) FROM ref.indicateur i
               WHERE NOT EXISTS (SELECT 1 FROM ref.unite u WHERE u.code = i.unite)
                  OR (i.theme IS NOT NULL AND NOT EXISTS
                      (SELECT 1 FROM ref.theme t
                       WHERE t.rubrique = i.rubrique AND t.code = i.theme))"""
        ).fetchone()[0]
        assert orphelins == 0


def test_nouvelle_rubrique_sans_migration_des_contraintes(base_module):
    with psycopg.connect(base_module["proprietaire"]) as conn:
        conn.execute(
            """INSERT INTO ref.rubrique (code, libelle, chemin, ordre, theme_obligatoire)
               VALUES ('ESSAI', 'Rubrique d''essai', '/essai', 99, true)"""
        )
        conn.execute(
            "INSERT INTO ref.theme (rubrique, code, libelle, ordre) "
            "VALUES ('ESSAI', 'LOGEMENT', 'Logement', 1)"
        )
        conn.execute("INSERT INTO ref.unite (code) VALUES ('euros_essai')")
        # Même code de thème que dans BESOINS : admis, il est rattaché à sa rubrique.
        conn.execute(_INSERER, ("ESSAI_OK", "euros_essai", "ESSAI", "LOGEMENT", None))
        conn.commit()

        refus = [
            # Thème obligatoire dans la rubrique.
            (("ESSAI_SANS", "pourcentage", "ESSAI", None, None), psycopg.errors.CheckViolation),
            # Angle de lecture réservé aux rubriques qui l'admettent (BESOINS).
            (
                ("ESSAI_ANGLE", "pourcentage", "ESSAI", "LOGEMENT", "COUT"),
                psycopg.errors.CheckViolation,
            ),
            (("QUI_ANGLE", "pourcentage", "QUI", None, "COUT"), psycopg.errors.CheckViolation),
            # Thème d'une autre rubrique, rubrique ou unité inconnues.
            (
                ("ESSAI_SOINS", "pourcentage", "ESSAI", "SOINS", None),
                psycopg.errors.ForeignKeyViolation,
            ),
            (
                ("INCONNUE", "pourcentage", "NULLE_PART", None, None),
                psycopg.errors.ForeignKeyViolation,
            ),
            (("UNITE", "litres", "QUI", None, None), psycopg.errors.ForeignKeyViolation),
        ]
        for valeurs, erreur in refus:
            with pytest.raises(erreur):
                conn.execute(_INSERER, valeurs)
            conn.rollback()


def test_api_lit_les_rubriques(urls_module):
    themes = client.get("/api/v1/indicateurs", params={"rubrique": "ESSAI"}).json()
    assert [i["code"] for i in themes] == ["ESSAI_OK"]
    reponse = client.get("/api/v1/indicateurs", params={"rubrique": "ESSAI", "theme": "LOGEMENT"})
    assert [i["code"] for i in reponse.json()] == ["ESSAI_OK"]
    # Thème connu mais d'une autre rubrique, rubrique inconnue : refusés.
    assert (
        client.get(
            "/api/v1/indicateurs", params={"rubrique": "ESSAI", "theme": "SOINS"}
        ).status_code
        == 422
    )
    assert client.get("/api/v1/indicateurs", params={"rubrique": "NULLE"}).status_code == 422
    assert client.get("/api/v1/indicateurs", params={"rubrique": "essai"}).status_code == 422
