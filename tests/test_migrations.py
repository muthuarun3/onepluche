import psycopg
import pytest

from demographie import migrations


def test_noms_des_migrations_valides():
    noms = [m.nom for m in migrations.lister()]
    assert noms == sorted(noms)
    assert noms[0] == "001_schemas.sql"


def test_migrations_idempotentes(base_test):
    with psycopg.connect(base_test["proprietaire"]) as conn:
        assert migrations.appliquer(conn) == []


def test_migration_modifiee_refusee(base_test, tmp_path):
    for m in migrations.lister():
        (tmp_path / m.nom).write_bytes(m.chemin.read_bytes())
    (tmp_path / "001_schemas.sql").write_text("-- modifiée\n", encoding="utf-8")
    with (
        psycopg.connect(base_test["proprietaire"]) as conn,
        pytest.raises(migrations.MigrationModifiee),
    ):
        migrations.appliquer(conn, tmp_path)


def test_referentiel_geographique(base_test):
    with psycopg.connect(base_test["proprietaire"]) as conn:
        comptes = dict(
            conn.execute("SELECT niveau, count(*) FROM ref.territoire GROUP BY niveau").fetchall()
        )
        assert comptes == {"FRANCE": 2, "REG": 18, "DEP": 101, "HORS_DEP": 2}
        orphelins = conn.execute(
            """
            SELECT count(*) FROM ref.territoire d
            JOIN ref.territoire r ON r.territoire_id = d.parent_id
            WHERE d.niveau = 'DEP' AND r.niveau <> 'REG'
            """
        ).fetchone()[0]
        assert orphelins == 0
        # Chaque région a au moins un département.
        regions_vides = conn.execute(
            """
            SELECT count(*) FROM ref.territoire r
            WHERE r.niveau = 'REG'
              AND NOT EXISTS (SELECT 1 FROM ref.territoire d WHERE d.parent_id = r.territoire_id)
            """
        ).fetchone()[0]
        assert regions_vides == 0


def test_contraintes_observation(base_test):
    """La base refuse elle-même une valeur incohérente."""
    with psycopg.connect(base_test["proprietaire"]) as conn:
        conn.execute(
            """
            INSERT INTO ref.indicateur (code, libelle, definition, unite, nature, source_id)
            SELECT 'POP_TEST', 'Test', 'Test', 'personnes', 'effectif', source_id
            FROM ref.source WHERE code = 'INSEE_EST'
            """
        )
        conn.execute(
            """
            INSERT INTO ingest.import (source_id, url, fichier_nom, sha256, taille_octets)
            SELECT source_id, 'https://exemple.fr/f.xlsx', 'f.xlsx', repeat('a', 64), 10
            FROM ref.source WHERE code = 'INSEE_EST'
            """
        )
        inserer = """
            INSERT INTO stat.observation
              (indicateur_id, territoire_id, periode, periode_type, sexe, age_min, age_max,
               valeur, statut, import_id)
            SELECT i.indicateur_id, t.territoire_id, '2026-01-01', '1ER_JANVIER', %s, %s, %s,
                   100, 'PROVISOIRE', (SELECT max(import_id) FROM ingest.import)
            FROM ref.indicateur i, ref.territoire t
            WHERE i.code = 'POP_TEST' AND t.niveau = 'DEP' AND t.code = '75'
        """
        conn.execute(inserer, ("T", None, None))
        # Doublon d'un total (NULL compris) refusé.
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(inserer, ("T", None, None))
        conn.rollback()
    with psycopg.connect(base_test["proprietaire"]) as conn:
        for sexe, age_min, age_max in [("X", None, None), ("F", 60, 20), ("F", None, 20)]:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(
                    "INSERT INTO stat.observation VALUES (1, 1, '2026-01-01', 'ANNEE', "
                    "%s, %s, %s, NULL, 1, 'DEFINITIF', 1)",
                    (sexe, age_min, age_max),
                )
            conn.rollback()


def test_role_lecture_limite_au_schema_api(base_test):
    with psycopg.connect(base_test["lecture"]) as conn:
        assert conn.execute("SELECT count(*) FROM api.territoire").fetchone()[0] == 123
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM ref.territoire")
        conn.rollback()
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("CREATE TEMP TABLE t (x int)")


def test_role_import_ne_modifie_pas_les_referentiels(base_test):
    with (
        psycopg.connect(base_test["import"]) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute("DELETE FROM ref.territoire")
