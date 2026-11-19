"""Routes /api/v1."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, BeforeValidator, Field

from demographie import donnees
from demographie.donnees import series, sources, territoires

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


def _nombre(valeur: object) -> object:
    """Entier quand la valeur est entière (effectifs), réel sinon (taux)."""
    if isinstance(valeur, Decimal):
        return int(valeur) if valeur == valeur.to_integral_value() else float(valeur)
    return valeur


Nombre = Annotated[int | float, BeforeValidator(_nombre)]
Niveau = Literal["FRANCE", "REG", "DEP"]
CodeTerritoire = Annotated[str, Query(pattern=r"^[0-9A-Z]{2,3}$")]
Annee = Annotated[int | None, Query(ge=1900, le=2100)]


class Indicateur(BaseModel):
    code: str
    libelle: str
    definition: str
    unite: str
    nature: str
    formule: str | None
    avertissement: str | None
    comparabilite: str | None
    source_code: str
    source_libelle: str
    source_url: str
    source_licence: str
    mis_a_jour_le: datetime | None


class TerritoireCourt(BaseModel):
    niveau: str
    code: str
    libelle: str


class Valeur(BaseModel):
    annee: int
    periode: date = Field(description="1er jour de la période (année, trimestre ou date)")
    periode_type: Literal["1ER_JANVIER", "ANNEE", "TRIMESTRE", "RP"]
    valeur: Nombre
    provisoire: bool


class Serie(BaseModel):
    indicateur: Indicateur
    territoire: TerritoireCourt
    valeurs: list[Valeur]


class Tranche(BaseModel):
    age_min: int
    age_max: int | None = Field(description="null pour la dernière tranche (« et plus »)")
    hommes: Nombre | None
    femmes: Nombre | None


class Structure(BaseModel):
    territoire: TerritoireCourt
    annee: int
    provisoire: bool
    source: str
    tranches: list[Tranche]


def _territoire(conn: psycopg.Connection, niveau: str, code: str) -> dict:
    trouve = territoires.trouver(conn, niveau, code)
    if trouve is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Territoire inconnu : {niveau} {code}")
    return trouve


@routeur.get("/indicateurs", response_model=list[Indicateur])
def lister_indicateurs(conn: Connexion) -> list[dict]:
    """Indicateurs disponibles, avec définition, source et date de mise à jour."""
    return series.indicateurs(conn)


@routeur.get("/series", response_model=Serie)
def lire_serie(
    conn: Connexion,
    indicateur: Annotated[str, Query(pattern=r"^[A-Z][A-Z0-9_]+$")],
    niveau: Niveau,
    code: CodeTerritoire,
    debut: Annee = None,
    fin: Annee = None,
    sexe: Literal["T", "F", "H"] = "T",
) -> dict:
    """Valeurs annuelles d'un indicateur pour un territoire.

    Population et structure par âge : au 1er janvier. Naissances, décès et taux :
    sur l'année civile. Espérance de vie : par sexe seulement (F ou H).
    """
    definition = series.indicateurs(conn, indicateur)
    if not definition:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Indicateur inconnu : {indicateur}")
    return {
        "indicateur": definition[0],
        "territoire": _territoire(conn, niveau, code),
        "valeurs": series.serie(conn, indicateur, niveau, code, debut, fin, sexe),
    }


@routeur.get("/structure", response_model=Structure)
def lire_structure(
    conn: Connexion, niveau: Niveau, code: CodeTerritoire, annee: Annee = None
) -> dict:
    """Population par sexe et tranche d'âge de 5 ans ; dernière année par défaut."""
    territoire = _territoire(conn, niveau, code)
    lignes = series.structure(conn, niveau, code, annee)
    if not lignes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune donnée pour cette année")
    tranches: dict[tuple, dict] = {}
    for ligne in lignes:
        cle = (ligne["age_min"], ligne["age_max"])
        tranche = tranches.setdefault(
            cle, {"age_min": cle[0], "age_max": cle[1], "hommes": None, "femmes": None}
        )
        tranche["hommes" if ligne["sexe"] == "H" else "femmes"] = ligne["valeur"]
    return {
        "territoire": territoire,
        "annee": lignes[0]["annee"],
        "provisoire": any(ligne["provisoire"] for ligne in lignes),
        "source": "INSEE, estimations de population au 1er janvier",
        "tranches": sorted(tranches.values(), key=lambda t: t["age_min"]),
    }


class EtatSource(BaseModel):
    source: str
    producteur: str
    source_libelle: str
    source_url: str
    licence: str
    fichier_nom: str | None
    dernier_statut: Literal["EN_COURS", "REJETE", "EN_ATTENTE", "PUBLIE"] | None
    dernier_essai: datetime | None
    derniere_publication: datetime | None
    millesime: str | None


@routeur.get("/sources", response_model=list[EtatSource])
def lister_sources(conn: Connexion) -> list[dict]:
    """Sources, fichiers importés, date de dernière publication et statut du dernier essai."""
    return sources.etat_imports(conn)
