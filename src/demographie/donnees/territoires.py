"""Lecture du référentiel géographique."""

from pathlib import Path

import psycopg

from demographie.db import charger_sql

_SQL = Path(__file__).parent / "sql"
# HORS_DEP : Français de l'étranger et collectivités d'outre-mer (rubrique VOTES).
NIVEAUX = ("FRANCE", "REG", "DEP", "HORS_DEP")


def lister(conn: psycopg.Connection, niveau: str | None = None) -> list[dict]:
    """Territoires, éventuellement filtrés par niveau, triés par niveau puis code."""
    if niveau is not None and niveau not in NIVEAUX:
        raise ValueError(f"Niveau inconnu : {niveau}")
    return conn.execute(charger_sql(_SQL, "territoires"), {"niveau": niveau}).fetchall()


def trouver(conn: psycopg.Connection, niveau: str, code: str) -> dict | None:
    """Un territoire et le libellé de son parent, ou None s'il n'existe pas."""
    parametres = {"niveau": niveau, "code": code}
    return conn.execute(charger_sql(_SQL, "territoire"), parametres).fetchone()


def enfants(conn: psycopg.Connection, niveau: str, code: str) -> list[dict]:
    """Territoires directement rattachés (régions de la France, départements d'une région)."""
    return conn.execute(charger_sql(_SQL, "enfants"), {"niveau": niveau, "code": code}).fetchall()
