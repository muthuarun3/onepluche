"""Base de test PostgreSQL réelle, créée puis détruite pour la session de tests.

Variable requise : DEMO_TEST_ADMIN_URL, connexion superutilisateur, par exemple
postgresql://postgres:postgres@localhost:5432/postgres
Sans elle, les tests qui ont besoin de la base sont ignorés.
"""

import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from demographie import migrations

RACINE = Path(__file__).resolve().parents[1]
MOT_DE_PASSE_TEST = "mot-de-passe-de-test"  # noqa: S105 (base jetable de test)


def _url_admin() -> str:
    url = os.environ.get("DEMO_TEST_ADMIN_URL")
    if not url:
        pytest.skip("DEMO_TEST_ADMIN_URL non défini : tests base ignorés")
    return url


def _url_pour(url_admin: str, base: str, role: str | None = None) -> str:
    params = conninfo_to_dict(url_admin)
    params["dbname"] = base
    if role:
        params["user"] = role
        params["password"] = MOT_DE_PASSE_TEST
    return make_conninfo(**params)


@pytest.fixture(scope="session")
def base_test() -> Iterator[dict[str, str]]:
    """Crée une base vide, les rôles et applique toutes les migrations."""
    url_admin = _url_admin()
    nom = f"demo_test_{secrets.token_hex(4)}"
    with psycopg.connect(url_admin, autocommit=True) as admin:
        admin.execute((RACINE / "sql" / "roles.sql").read_text(encoding="utf-8"))
        for role in ("demo_proprietaire", "demo_import", "demo_lecture"):
            admin.execute(f"ALTER ROLE {role} PASSWORD '{MOT_DE_PASSE_TEST}'")
        admin.execute(f"CREATE DATABASE {nom} OWNER demo_proprietaire")
    try:
        urls = {
            "proprietaire": _url_pour(url_admin, nom, "demo_proprietaire"),
            "import": _url_pour(url_admin, nom, "demo_import"),
            "lecture": _url_pour(url_admin, nom, "demo_lecture"),
        }
        with psycopg.connect(urls["proprietaire"]) as conn:
            migrations.appliquer(conn)
        yield urls
    finally:
        with psycopg.connect(url_admin, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {nom} WITH (FORCE)")


@pytest.fixture
def urls_db(base_test, monkeypatch) -> dict[str, str]:
    """Rend les URL de test visibles par demographie.config."""
    monkeypatch.setenv("DEMO_DB_PROPRIETAIRE_URL", base_test["proprietaire"])
    monkeypatch.setenv("DEMO_DB_IMPORT_URL", base_test["import"])
    monkeypatch.setenv("DEMO_DB_LECTURE_URL", base_test["lecture"])
    return base_test
