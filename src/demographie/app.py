"""Assemblage de l'application : API, pages web, route de santé.

Lancement : uvicorn demographie.app:app
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from demographie import __version__
from demographie.api import v1

app = FastAPI(
    title="Démographie France",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.include_router(v1.routeur)

_ENTETES_SECURITE = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


@app.middleware("http")
async def entetes_securite(request: Request, call_next):
    reponse = await call_next(request)
    for nom, valeur in _ENTETES_SECURITE.items():
        reponse.headers.setdefault(nom, valeur)
    return reponse


@app.get("/sante", include_in_schema=False)
def sante() -> JSONResponse:
    """Vérification de vie utilisée par la supervision ; ne touche pas la base."""
    return JSONResponse({"statut": "ok", "version": __version__})
