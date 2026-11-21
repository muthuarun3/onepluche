"""Lecture des indicateurs, des séries annuelles et de la structure par âge."""

from pathlib import Path

import psycopg

from demographie.db import charger_sql

_SQL = Path(__file__).parent / "sql"


def indicateurs(
    conn: psycopg.Connection,
    code: str | None = None,
    rubrique: str | None = None,
    theme: str | None = None,
) -> list[dict]:
    """Définitions des indicateurs, avec leur source et la date de dernière mise à jour."""
    parametres = {"code": code, "rubrique": rubrique, "theme": theme}
    return conn.execute(charger_sql(_SQL, "indicateurs"), parametres).fetchall()


def fiche(
    conn: psycopg.Connection, niveau: str, code: str, rubrique: str, theme: str | None = None
) -> list[dict]:
    """Dernière valeur de chaque indicateur d'une rubrique pour un territoire, avec la
    valeur France de la même période."""
    parametres = {"niveau": niveau, "code": code, "rubrique": rubrique, "theme": theme}
    return conn.execute(charger_sql(_SQL, "fiche"), parametres).fetchall()


def serie(
    conn: psycopg.Connection,
    indicateur: str,
    niveau: str,
    code: str,
    debut: int | None = None,
    fin: int | None = None,
    sexe: str = "T",
) -> list[dict]:
    """Valeurs annuelles d'un indicateur pour un territoire, par année croissante."""
    parametres = {
        "indicateur": indicateur,
        "niveau": niveau,
        "code": code,
        "debut": debut,
        "fin": fin,
        "sexe": sexe,
    }
    return conn.execute(charger_sql(_SQL, "serie"), parametres).fetchall()


def chiffres_cles(conn: psycopg.Connection, niveau: str, code: str) -> dict[str, dict]:
    """Dernière valeur connue de chaque indicateur, par code d'indicateur."""
    lignes = conn.execute(charger_sql(_SQL, "chiffres_cles"), {"niveau": niveau, "code": code})
    return {ligne["indicateur"]: ligne for ligne in lignes.fetchall()}


def structure(
    conn: psycopg.Connection, niveau: str, code: str, annee: int | None = None
) -> list[dict]:
    """Population par sexe et tranche d'âge ; dernière année disponible par défaut."""
    parametres = {"niveau": niveau, "code": code, "annee": annee}
    return conn.execute(charger_sql(_SQL, "structure"), parametres).fetchall()


def repartition(
    conn: psycopg.Connection, indicateur: str, niveau: str, code: str, annee: int | None = None
) -> list[dict]:
    """Effectif par modalité (catégorie, secteur…) et total ; dernière année par défaut."""
    parametres = {"indicateur": indicateur, "niveau": niveau, "code": code, "annee": annee}
    return conn.execute(charger_sql(_SQL, "repartition"), parametres).fetchall()
