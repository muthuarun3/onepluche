"""Routes /api/v1."""

from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from demographie import donnees
from demographie.donnees import territoires

routeur = APIRouter(prefix="/api/v1", tags=["v1"])
Connexion = Annotated[psycopg.Connection, Depends(donnees.connexion_lecture)]


class Territoire(BaseModel):
    code: str
    niveau: Literal["FRANCE", "REG", "DEP"]
    libelle: str
    parent_niveau: str | None
    parent_code: str | None
    cog_millesime: int


@routeur.get("/territoires", response_model=list[Territoire])
def lister_territoires(
    conn: Connexion,
    niveau: Annotated[Literal["FRANCE", "REG", "DEP"] | None, Query()] = None,
) -> list[dict]:
    """France, régions et départements, avec leur rattachement."""
    return territoires.lister(conn, niveau)
