"""Toutes les lectures de données : seul module autorisé à écrire du SQL de lecture.

Les requêtes vivent dans des fichiers .sql (sous-dossier sql/) et sont toujours
paramétrées. Ce module utilise exclusivement le rôle « lecture ».
"""

from collections.abc import Iterator

import psycopg

from demographie import db


def connexion_lecture() -> Iterator[psycopg.Connection]:
    """Connexion en lecture seule, utilisable comme dépendance FastAPI."""
    with db.connexion("lecture") as conn:
        yield conn
