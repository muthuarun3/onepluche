"""Alertes par « battement » (Healthchecks.io ou compatible), sans serveur de courriel.

Chaque exécution d'import signale son début, puis son succès ou son échec avec un
résumé. Le service prévient par courriel en cas d'échec, et aussi si aucun signal
n'arrive (tâche arrêtée, serveur éteint). Sans URL configurée, rien n'est envoyé.
"""

import urllib.request

DELAI = 10
TAILLE_MAX = 10_000  # Healthchecks conserve les 10 premiers ko du corps


def signaler(url: str | None, etat: str, resume: str = "") -> bool:
    """etat : "debut", "succes" ou "echec". Renvoie False si le signal n'a pas pu partir.

    Une alerte ne doit jamais faire échouer l'import : les erreurs réseau sont avalées.
    """
    if not url:
        return False
    if not url.startswith("https://"):
        raise ValueError("L'URL de battement doit être en https")
    suffixe = {"debut": "/start", "succes": "", "echec": "/fail"}[etat]
    corps = resume.encode("utf-8")[:TAILLE_MAX]
    requete = urllib.request.Request(  # noqa: S310 (https imposé ci-dessus)
        url.rstrip("/") + suffixe,
        data=corps,
        headers={"User-Agent": "onepluche-demographie/0.1", "Content-Type": "text/plain"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=DELAI):  # noqa: S310
            return True
    except OSError:
        return False
