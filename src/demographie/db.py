"""Connexions PostgreSQL, une par rôle.

- « proprietaire » : migrations uniquement ;
- « import »       : écriture des imports ;
- « lecture »      : application web et API, lecture seule (imposée par la base).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from demographie import config

ROLES = ("proprietaire", "import", "lecture")


@contextmanager
def connexion(role: str, url: str | None = None) -> Iterator[psycopg.Connection]:
    """Ouvre une connexion pour un rôle ; validée en sortie normale, annulée sinon."""
    if role not in ROLES:
        raise ValueError(f"Rôle inconnu : {role}")
    with psycopg.connect(url or config.charger().url(role), row_factory=dict_row) as conn:
        yield conn


def charger_sql(dossier: Path, nom: str) -> str:
    """Charge une requête SQL stockée dans un fichier .sql, par son nom."""
    if not nom.replace("_", "").isalnum():
        raise ValueError(f"Nom de requête invalide : {nom}")
    return (dossier / f"{nom}.sql").read_text(encoding="utf-8")
