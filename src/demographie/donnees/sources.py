"""Lecture de l'état des sources : dernier import de chaque fichier."""

from pathlib import Path

import psycopg

from demographie.db import charger_sql

_SQL = Path(__file__).parent / "sql"


def etat_imports(conn: psycopg.Connection) -> list[dict]:
    """Une ligne par fichier importé (ou par source jamais importée)."""
    return conn.execute(charger_sql(_SQL, "etat_imports")).fetchall()


def releves_programmes(conn: psycopg.Connection) -> list[dict]:
    """Dernier relevé de chaque programme présidentiel suivi (veille du lundi)."""
    return conn.execute(charger_sql(_SQL, "programmes_releves")).fetchall()
