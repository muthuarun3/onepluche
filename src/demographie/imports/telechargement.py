"""Téléchargements HTTPS vers les sites des producteurs, avec empreinte SHA-256."""

import hashlib
import http.client
import json
import os
import tempfile
import urllib.request
from pathlib import Path

AGENT = "onepluche-demographie/0.1"
TAILLE_MAX = 200 * 1024 * 1024
DELAI = 120


class TelechargementRefuse(RuntimeError):
    """URL non autorisée ou fichier trop volumineux."""


def _ouvrir(url: str):
    if not url.startswith("https://"):
        raise TelechargementRefuse(f"Seules les URL https sont acceptées : {url}")
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT})  # noqa: S310
    return urllib.request.urlopen(requete, timeout=DELAI)  # noqa: S310


def lire_page(url: str) -> str:
    """Contenu HTML d'une page (pour découvrir les fichiers publiés)."""
    with _ouvrir(url) as reponse:
        return reponse.read(5 * 1024 * 1024).decode("utf-8", errors="replace")


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def telecharger(url: str, dossier: Path) -> Path:
    """Télécharge dans un fichier temporaire du dossier donné et renvoie son chemin."""
    dossier.mkdir(parents=True, exist_ok=True)
    descripteur, nom = tempfile.mkstemp(dir=dossier, suffix=".part")
    chemin = Path(nom)
    try:
        with os.fdopen(descripteur, "wb") as sortie, _ouvrir(url) as reponse:
            total = 0
            for bloc in iter(lambda: reponse.read(1 << 20), b""):
                total += len(bloc)
                if total > TAILLE_MAX:
                    raise TelechargementRefuse(f"Fichier trop volumineux : {url}")
                sortie.write(bloc)
    except BaseException:
        chemin.unlink(missing_ok=True)
        raise
    return chemin


def lire_json(url: str, taille_max: int = 50 * 1024 * 1024) -> object:
    """Réponse JSON d'une API (Melodi…), limitée en taille."""
    with _ouvrir(url) as reponse:
        contenu = reponse.read(taille_max + 1)
    if len(contenu) > taille_max:
        raise TelechargementRefuse(f"Réponse trop volumineuse : {url}")
    return json.loads(contenu)


def lire_plage(url: str, debut: int, fin: int, essais: int = 3) -> bytes:
    """Octets ``debut`` à ``fin`` (inclus) d'un fichier, par une requête HTTP Range : pour ne
    lire qu'une partie d'un gros fichier (la France dans une grille mondiale). Une réponse
    coupée en route est redemandée (``essais`` fois en tout)."""
    if not url.startswith("https://"):
        raise TelechargementRefuse(f"Seules les URL https sont acceptées : {url}")
    if fin - debut + 1 > TAILLE_MAX:
        raise TelechargementRefuse(f"Plage trop grande : {url}")
    entetes = {"User-Agent": AGENT, "Range": f"bytes={debut}-{fin}"}
    for essai in range(essais):
        requete = urllib.request.Request(url, headers=entetes)  # noqa: S310
        try:
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:  # noqa: S310
                if reponse.status != 206:
                    raise TelechargementRefuse(f"Le serveur ne sert pas de plage d'octets : {url}")
                contenu = reponse.read(fin - debut + 2)
        except (OSError, http.client.IncompleteRead):
            if essai == essais - 1:
                raise
            continue
        if len(contenu) == fin - debut + 1:
            return contenu
    raise TelechargementRefuse(f"Plage incomplète après {essais} essais : {url}")
