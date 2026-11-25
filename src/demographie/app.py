"""Assemblage de l'application : API, pages web, route de santé.

Lancement : uvicorn demographie.app:app
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from demographie import __version__
from demographie.api import v1
from demographie.web import argent, avenir, besoins, pages, programmes, securite, travail, vivre

app = FastAPI(
    title="On épluche",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(v1.routeur)
app.include_router(pages.routeur)
app.include_router(besoins.routeur)
app.include_router(avenir.routeur)
app.include_router(securite.routeur)
app.include_router(travail.routeur)
app.include_router(vivre.routeur)
app.include_router(argent.routeur)
app.include_router(programmes.routeur)
app.mount("/static", StaticFiles(directory=pages.STATIQUE), name="static")

_ENTETES_SECURITE = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}
# Scripts uniquement servis par l'application. Les styles en ligne restent permis :
# les infobulles d'ECharts en posent. La documentation /api/docs (Swagger, chargé
# depuis un CDN) n'est pas concernée.
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'"
)


@app.middleware("http")
async def entetes_securite(request: Request, call_next):
    reponse = await call_next(request)
    for nom, valeur in _ENTETES_SECURITE.items():
        reponse.headers.setdefault(nom, valeur)
    if not request.url.path.startswith("/api/docs"):
        reponse.headers.setdefault("Content-Security-Policy", _CSP)
    return reponse


@app.get("/sante", include_in_schema=False)
def sante() -> JSONResponse:
    """Vérification de vie utilisée par la supervision ; ne touche pas la base."""
    return JSONResponse({"statut": "ok", "version": __version__})
