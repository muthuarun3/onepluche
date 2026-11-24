"""Lecture des projections (rubrique « Quel avenir pour les Français ? »)."""

from pathlib import Path

import psycopg

from demographie.db import charger_sql

_SQL = Path(__file__).parent / "sql"


def scenarios(conn: psycopg.Connection) -> list[dict]:
    """Scénarios connus, dans l'ordre d'affichage."""
    return conn.execute(charger_sql(_SQL, "scenarios")).fetchall()


def population(conn: psycopg.Connection, niveau: str, code: str) -> list[dict]:
    """Population projetée (Omphale) par scénario et année, avec les parts et ratios."""
    parametres = {"niveau": niveau, "code": code}
    return conn.execute(charger_sql(_SQL, "projection_population"), parametres).fetchall()


def pyramide(
    conn: psycopg.Connection, niveau: str, code: str, annees: list[int], scenario: str
) -> list[dict]:
    """Population projetée par sexe et tranche d'âge pour les années demandées."""
    parametres = {"niveau": niveau, "code": code, "annees": annees, "scenario": scenario}
    return conn.execute(charger_sql(_SQL, "projection_pyramide"), parametres).fetchall()


def valeurs(
    conn: psycopg.Connection,
    indicateur: str,
    niveau: str,
    code: str,
    scenario: str | None = None,
    sexe: str = "T",
    par_age: bool = False,
) -> list[dict]:
    """Valeurs projetées d'un indicateur pour un territoire ; tous âges sauf `par_age`."""
    parametres = {
        "indicateur": indicateur,
        "niveau": niveau,
        "code": code,
        "scenario": scenario,
        "sexe": sexe,
        "par_age": par_age,
    }
    return conn.execute(charger_sql(_SQL, "projection"), parametres).fetchall()


def climat(conn: psycopg.Connection, niveau: str, code: str) -> list[dict]:
    """Climat projeté (écart à 1995-2014) : médiane et fourchette par scénario et période."""
    parametres = {"niveau": niveau, "code": code}
    return conn.execute(charger_sql(_SQL, "projection_climat"), parametres).fetchall()


def classement_population(
    conn: psycopg.Connection, scenario: str, annee: int, depart: int
) -> list[dict]:
    """Population projetée de chaque département (et de la France, « FR ») pour un
    scénario et une année : population, évolution depuis `depart`, part des 75 ans ou plus,
    seniors pour 100 actifs. Départements sans projection : valeurs NULL."""
    parametres = {"scenario": scenario, "annee": annee, "depart": depart}
    return conn.execute(charger_sql(_SQL, "classement_population"), parametres).fetchall()


def classement_climat(
    conn: psycopg.Connection, indicateur: str, scenario: str, debut: int
) -> list[dict]:
    """Climat projeté de chaque département (et de la métropole, « FM ») pour un
    indicateur, un scénario et une période : médiane (`valeur`), bas et haut."""
    parametres = {"indicateur": indicateur, "scenario": scenario, "debut": debut}
    return conn.execute(charger_sql(_SQL, "classement_climat"), parametres).fetchall()
