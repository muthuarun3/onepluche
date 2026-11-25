"""Accès réservé au petit cercle par lien secret.

Le lien à partager est https://<domaine>/?cle=<DEMO_CLE_ACCES>. Au premier passage, la clé
est échangée contre un cookie durable, puis l'adresse est nettoyée (la clé ne reste ni dans
la barre d'adresse ni dans l'historique). Sans cookie valide ni clé, le site est fermé.

Le cookie ne contient pas la clé mais une empreinte HMAC de celle-ci : changer
DEMO_CLE_ACCES (puis redémarrer) invalide d'un coup tous les cookies distribués.

Sans DEMO_CLE_ACCES (développement local, tests), le site reste ouvert.
"""

import hashlib
import hmac
import os
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

VARIABLE = "DEMO_CLE_ACCES"
COOKIE = "onepluche_acces"
PARAMETRE = "cle"
# 400 jours : durée maximale qu'acceptent les navigateurs pour un cookie.
DUREE_COOKIE = 400 * 24 * 3600
# Chemins servis sans clé : supervision, consignes aux robots, feuille de style et scripts
# (code de l'appli, aucune donnée ; la page « site fermé » a besoin de la feuille de style).
CHEMINS_PUBLICS = ("/sante", "/robots.txt")
PREFIXES_PUBLICS = ("/static/",)

ROBOTS = "User-agent: *\nDisallow: /\n"

PAGE_FERMEE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>On épluche — accès sur invitation</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <main class="site-ferme">
    <p class="marque">On épluche</p>
    <h1>Accès sur invitation</h1>
    <p>Ce site est réservé à un petit cercle. Pour y entrer, ouvrez le lien d'invitation
      qu'on vous a transmis : votre navigateur s'en souviendra ensuite.</p>
    <p>Si le lien ne fonctionne plus, demandez-en un nouveau à la personne qui vous l'a
      envoyé.</p>
    <p class="muet">Présentation publique du projet :
      <a href="https://onepluche.neocities.org">onepluche.neocities.org</a></p>
  </main>
</body>
</html>
"""


def cle_configuree() -> str | None:
    """Clé d'accès lue à chaque requête (les tests peuvent la changer à la volée)."""
    return os.environ.get(VARIABLE, "").strip() or None


def jeton(cle: str) -> str:
    """Valeur du cookie : empreinte de la clé, jamais la clé elle-même."""
    return hmac.new(cle.encode(), b"onepluche-acces-v1", hashlib.sha256).hexdigest()


def _public(chemin: str) -> bool:
    return chemin in CHEMINS_PUBLICS or chemin.startswith(PREFIXES_PUBLICS)


def _adresse_sans_cle(request: Request) -> str:
    reste = [(k, v) for k, v in request.query_params.multi_items() if k != PARAMETRE]
    return request.url.path + (f"?{urlencode(reste)}" if reste else "")


def _refus(request: Request):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"detail": "Accès réservé : ouvrez d'abord le lien d'invitation."}, status_code=401
        )
    return HTMLResponse(PAGE_FERMEE, status_code=403)


async def controler(request: Request, call_next):
    """Intergiciel : laisse passer, échange la clé contre un cookie, ou ferme."""
    if request.url.path == "/robots.txt":
        return PlainTextResponse(ROBOTS)
    cle = cle_configuree()
    if cle is None or _public(request.url.path):
        return await call_next(request)

    attendu = jeton(cle)
    proposee = request.query_params.get(PARAMETRE)
    if proposee is not None:
        if not hmac.compare_digest(proposee.encode(), cle.encode()):
            return _refus(request)
        reponse = RedirectResponse(_adresse_sans_cle(request), status_code=303)
        reponse.set_cookie(
            COOKIE,
            attendu,
            max_age=DUREE_COOKIE,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
        return reponse

    if hmac.compare_digest(request.cookies.get(COOKIE, "").encode(), attendu.encode()):
        return await call_next(request)
    return _refus(request)
