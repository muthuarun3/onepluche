"""Base de test PostgreSQL réelle, créée puis détruite pour la session de tests.

Variable requise : DEMO_TEST_ADMIN_URL, connexion superutilisateur, par exemple
postgresql://postgres:postgres@localhost:5432/postgres
Sans elle, les tests qui ont besoin de la base sont ignorés.
"""

import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from demographie import migrations

RACINE = Path(__file__).resolve().parents[1]
MOT_DE_PASSE_TEST = "mot-de-passe-de-test"  # noqa: S105 (base jetable de test)
FIXTURES = RACINE / "tests" / "fixtures"


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


@contextmanager
def _base_jetable(url_admin: str) -> Iterator[dict[str, str]]:
    """Crée une base vide, les rôles et applique toutes les migrations ; la détruit après."""
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


def _exposer(urls: dict[str, str], monkeypatch, dossier_brut: Path) -> None:
    monkeypatch.setenv("DEMO_DB_PROPRIETAIRE_URL", urls["proprietaire"])
    monkeypatch.setenv("DEMO_DB_IMPORT_URL", urls["import"])
    monkeypatch.setenv("DEMO_DB_LECTURE_URL", urls["lecture"])
    monkeypatch.setenv("DEMO_DONNEES_BRUTES", str(dossier_brut))


@pytest.fixture(scope="session")
def base_test() -> Iterator[dict[str, str]]:
    """Base partagée par la session : migrations appliquées, aucune donnée importée."""
    with _base_jetable(_url_admin()) as urls:
        yield urls


@pytest.fixture
def urls_db(base_test, monkeypatch, tmp_path) -> dict[str, str]:
    """Rend les URL de la base partagée visibles par demographie.config."""
    _exposer(base_test, monkeypatch, tmp_path / "brut")
    return base_test


@pytest.fixture(scope="module")
def base_module() -> Iterator[dict[str, str]]:
    """Base propre à un module de tests (imports qui modifient les données)."""
    with _base_jetable(_url_admin()) as urls:
        yield urls


@pytest.fixture
def urls_module(base_module, monkeypatch, tmp_path_factory) -> dict[str, str]:
    _exposer(base_module, monkeypatch, tmp_path_factory.getbasetemp() / "brut")
    return base_module
