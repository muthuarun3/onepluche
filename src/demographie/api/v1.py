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
    # Appli 2 : rubrique (QUI ou BESOINS), thème et angle de lecture (accès, coût, manque).
    rubrique: str = "QUI"
    theme: str | None = None
    angle: str | None = None


class TerritoireCourt(BaseModel):
    niveau: str
    code: str
    libelle: str


class Valeur(BaseModel):
    annee: int
    periode: date = Field(description="1er jour de la période (année, trimestre ou date)")
    periode_type: Literal["1ER_JANVIER", "ANNEE", "TRIMESTRE", "MOIS", "RP"]
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


Rubrique = Literal["QUI", "BESOINS"]
Theme = Literal[
    "LOGEMENT", "ENERGIE", "EAU", "ALIMENTATION", "TRANSPORTS", "SOINS", "NUMERIQUE", "GARDE"
]


@routeur.get("/indicateurs", response_model=list[Indicateur])
def lister_indicateurs(
    conn: Connexion, rubrique: Rubrique | None = None, theme: Theme | None = None
) -> list[dict]:
    """Indicateurs disponibles, avec définition, source et date de mise à jour.

    `rubrique` : QUI (« Qui sont les Français ? ») ou BESOINS (« De quoi les Français ont
    besoin ? ») ; `theme` : thème de la rubrique BESOINS (LOGEMENT, ENERGIE, SOINS…).
    """
    return series.indicateurs(conn, rubrique=rubrique, theme=theme)


class ValeurFrance(BaseModel):
    code: Literal["FR", "FM"] = Field(description="FR : France entière ; FM : métropole")
    valeur: Nombre
    provisoire: bool


class LigneFiche(BaseModel):
    indicateur: Indicateur
    annee: int
    periode: date
    periode_type: Literal["1ER_JANVIER", "ANNEE", "TRIMESTRE", "MOIS", "RP"]
    valeur: Nombre
    provisoire: bool
    france: ValeurFrance | None = Field(description="même période ; null si non publiée")


class Fiche(BaseModel):
    territoire: TerritoireCourt
    rubrique: str
    theme: str | None
    lignes: list[LigneFiche]


@routeur.get("/fiche", response_model=Fiche)
def lire_fiche(
    conn: Connexion,
    niveau: Niveau,
    code: CodeTerritoire,
    rubrique: Rubrique = "BESOINS",
    theme: Theme | None = None,
) -> dict:
    """Dernière valeur de chaque indicateur d'une rubrique (ou d'un thème) pour un
    territoire, avec la valeur France de la même période et la source de l'indicateur.

    Triée par thème puis par angle de lecture (accès, coût, manque).
    """
    territoire = _territoire(conn, niveau, code)
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=rubrique)}
    lignes = []
    for ligne in series.fiche(conn, niveau, code, rubrique, theme):
        france = None
        if ligne["france_code"] is not None:
            france = {
                "code": ligne["france_code"],
                "valeur": ligne["france_valeur"],
                "provisoire": ligne["france_provisoire"],
            }
        lignes.append(
            {
                "indicateur": definitions[ligne["indicateur"]],
                **{k: ligne[k] for k in ("annee", "periode", "periode_type", "valeur")},
                "provisoire": ligne["provisoire"],
                "france": france,
            }
        )
    return {"territoire": territoire, "rubrique": rubrique, "theme": theme, "lignes": lignes}


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


class Part(BaseModel):
    modalite: str
    libelle: str
    age_min: int | None
    age_max: int | None
    valeur: Nombre
    part: float | None = Field(description="en % du total de la même tranche d'âge")


class Repartition(BaseModel):
    indicateur: Indicateur
    territoire: TerritoireCourt
    annee: int
    periode_type: str
    provisoire: bool
    parts: list[Part]


@routeur.get("/repartition", response_model=Repartition)
def lire_repartition(
    conn: Connexion,
    indicateur: Annotated[str, Query(pattern=r"^[A-Z][A-Z0-9_]+$")],
    niveau: Niveau,
    code: CodeTerritoire,
    annee: Annee = None,
) -> dict:
    """Répartition d'un effectif entre catégories (catégories socioprofessionnelles,
    secteurs d'activité, statut d'activité…) ; dernière année par défaut.

    Certaines modalités s'emboîtent (ex. « actifs » = « en emploi » + « chômeurs ») :
    les parts ne s'additionnent pas toujours à 100 %.
    """
    definition = series.indicateurs(conn, indicateur)
    if not definition:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Indicateur inconnu : {indicateur}")
    territoire = _territoire(conn, niveau, code)
    lignes = series.repartition(conn, indicateur, niveau, code, annee)
    if not lignes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune répartition pour cette demande")
    parts = [
        {
            **{k: ligne[k] for k in ("modalite", "libelle", "age_min", "age_max", "valeur")},
            "part": round(float(100 * ligne["valeur"] / ligne["total"]), 1)
            if ligne["total"]
            else None,
        }
        for ligne in lignes
    ]
    return {
        "indicateur": definition[0],
        "territoire": territoire,
        "annee": lignes[0]["annee"],
        "periode_type": lignes[0]["periode_type"],
        "provisoire": any(ligne["provisoire"] for ligne in lignes),
        "parts": parts,
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
