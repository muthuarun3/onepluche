"""Application des migrations SQL numérotées (sql/migrations/NNN_nom.sql).

Chaque fichier est appliqué une seule fois, dans sa propre transaction.
Son empreinte est enregistrée : un fichier déjà appliqué ne doit plus être modifié,
on ajoute une nouvelle migration à la place.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import tuple_row

DOSSIER_SQL = Path(__file__).resolve().parents[2] / "sql"
DOSSIER_MIGRATIONS = DOSSIER_SQL / "migrations"
_NOM_VALIDE = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")


class MigrationModifiee(RuntimeError):
    """Un fichier déjà appliqué a changé depuis son application."""


@dataclass(frozen=True)
class Migration:
    nom: str
    chemin: Path

    @property
    def contenu(self) -> str:
        return self.chemin.read_text(encoding="utf-8")

    @property
    def empreinte(self) -> str:
        return hashlib.sha256(self.chemin.read_bytes()).hexdigest()


def lister(dossier: Path = DOSSIER_MIGRATIONS) -> list[Migration]:
    fichiers = sorted(p for p in dossier.glob("*.sql"))
    invalides = [p.name for p in fichiers if not _NOM_VALIDE.match(p.name)]
    if invalides:
        raise ValueError(f"Noms de migration invalides : {', '.join(invalides)}")
    numeros = [p.name[:3] for p in fichiers]
    if len(numeros) != len(set(numeros)):
        raise ValueError("Deux migrations portent le même numéro")
    return [Migration(p.name, p) for p in fichiers]


def _preparer_journal(conn: psycopg.Connection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS admin")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin.migration (
          nom          text PRIMARY KEY,
          empreinte    char(64)    NOT NULL,
          appliquee_le timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    conn.commit()


def appliquer(conn: psycopg.Connection, dossier: Path = DOSSIER_MIGRATIONS) -> list[str]:
    """Applique les migrations manquantes et renvoie leurs noms."""
    _preparer_journal(conn)
    with conn.cursor(row_factory=tuple_row) as cur:
        deja = dict(cur.execute("SELECT nom, empreinte FROM admin.migration").fetchall())
    appliquees = []
    for migration in lister(dossier):
        if migration.nom in deja:
            if deja[migration.nom] != migration.empreinte:
                raise MigrationModifiee(
                    f"{migration.nom} a été modifiée après son application ; "
                    "créez une nouvelle migration au lieu de la modifier."
                )
            continue
        with conn.transaction():
            conn.execute(migration.contenu)
            conn.execute(
                "INSERT INTO admin.migration (nom, empreinte) VALUES (%s, %s)",
                (migration.nom, migration.empreinte),
            )
        appliquees.append(migration.nom)
    return appliquees
