"""Veille des programmes présidentiels : relevé hebdomadaire des textes suivis.

Pour chaque adresse de `programmes/<élection>/suivis.toml` : téléchargement, empreinte
SHA-256, copie gardée sur le disque du serveur (jamais dans le dépôt public), une ligne dans
`ingest.programme_releve`. Une empreinte différente du relevé précédent de la même adresse
veut dire que le texte a changé : la commande le signale pour qu'une fiche soit mise à jour
par PR. La veille n'écrit jamais dans une fiche et n'efface rien.
"""

import shutil
import tomllib
import urllib.error
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import psycopg
from pydantic import BaseModel, ConfigDict, StringConstraints

from demographie.imports import telechargement

Identifiant = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
Lien = Annotated[str, StringConstraints(pattern=r"^https://\S+$")]


class Suivi(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidat: Identifiant
    version: Identifiant
    url: Lien


class _Suivis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suivis: list[Suivi] = []


@dataclass(frozen=True)
class Releve:
    suivi: Suivi
    sha256: str | None
    change: bool
    message: str | None

    @property
    def en_erreur(self) -> bool:
        return self.sha256 is None

    def ligne(self) -> str:
        nom = f"{self.suivi.candidat} {self.suivi.version}"
        if self.en_erreur:
            return f"ERREUR   {nom} : {self.message} ({self.suivi.url})"
        if self.change:
            return f"MODIFIÉ  {nom} : nouvelle empreinte {self.sha256[:12]} ({self.suivi.url})"
        return f"inchangé {nom} ({self.sha256[:12]})"


def lire_suivis(dossier_election: Path) -> list[Suivi]:
    chemin = dossier_election / "suivis.toml"
    with chemin.open("rb") as fichier:
        return _Suivis.model_validate(tomllib.load(fichier)).suivis


def _empreinte_precedente(conn: psycopg.Connection, url: str) -> str | None:
    ligne = conn.execute(
        "SELECT sha256 FROM ingest.programme_releve"
        " WHERE url = %s AND sha256 IS NOT NULL ORDER BY releve_le DESC, releve_id DESC LIMIT 1",
        (url,),
    ).fetchone()
    return None if ligne is None else ligne["sha256"]


def _ranger(fichier: Path, copies: Path, election: str, suivi: Suivi, sha: str) -> None:
    """Garde la copie sous son empreinte ; une copie déjà connue n'est pas dupliquée."""
    extension = Path(suivi.url.split("?")[0]).suffix.lower()
    if not extension or len(extension) > 6:
        extension = ".html"
    cible = copies / election / suivi.candidat / f"{suivi.version}-{sha}{extension}"
    cible.parent.mkdir(parents=True, exist_ok=True)
    if cible.exists():
        fichier.unlink()
    else:
        shutil.move(fichier, cible)


def veiller(
    conn: psycopg.Connection,
    dossier_election: Path,
    copies: Path,
    telecharger: Callable[[str, Path], Path] | None = None,
) -> list[Releve]:
    """Relève chaque adresse suivie et renvoie un relevé par adresse."""
    telecharger = telecharger or telechargement.telecharger
    election = dossier_election.name
    releves = []
    for suivi in lire_suivis(dossier_election):
        precedente = _empreinte_precedente(conn, suivi.url)
        statut, taille, sha, message = None, None, None, None
        try:
            fichier = telecharger(suivi.url, copies / ".en-cours")
            taille = fichier.stat().st_size
            sha = telechargement.empreinte(fichier)
            statut = 200
            _ranger(fichier, copies, election, suivi, sha)
        except urllib.error.HTTPError as erreur:
            statut, message = erreur.code, f"erreur HTTP {erreur.code}"
        except (OSError, telechargement.TelechargementRefuse) as erreur:
            message = f"téléchargement impossible : {erreur}"
        change = sha is not None and precedente is not None and sha != precedente
        conn.execute(
            "INSERT INTO ingest.programme_releve"
            " (election, candidat, version, url, statut_http, taille_octets, sha256, change,"
            "  message)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                election,
                suivi.candidat,
                suivi.version,
                suivi.url,
                statut,
                taille,
                sha,
                change,
                message,
            ),
        )
        releves.append(Releve(suivi=suivi, sha256=sha, change=change, message=message))
    return releves
