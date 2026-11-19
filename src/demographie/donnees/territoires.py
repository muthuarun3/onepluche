"""Lecture du référentiel géographique."""

from pathlib import Path

import psycopg

from demographie.db import charger_sql

_SQL = Path(__file__).parent / "sql"
NIVEAUX = ("FRANCE", "REG", "DEP")


def lister(conn: psycopg.Connection, niveau: str | None = None) -> list[dict]:
    """Territoires, éventuellement filtrés par niveau, triés par niveau puis code."""
    if niveau is not None and niveau not in NIVEAUX:
        raise ValueError(f"Niveau inconnu : {niveau}")
    return conn.execute(charger_sql(_SQL, "territoires"), {"niveau": niveau}).fetchall()
