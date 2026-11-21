"""Sources communales ramenées au département, avant leur chargement.

Les communes ne sont pas dans le référentiel (maille du projet : le département). Un
connecteur qui lit des valeurs communales les agrège ici : somme (logements, locaux…)
ou moyenne pondérée par un poids communal (loyers, accessibilité aux soins…).
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from demographie.imports.modele import FichierIllisible

# Départements et régions d'outre-mer : hors de la France métropolitaine (« FM »).
DROM = frozenset({"971", "972", "973", "974", "976"})


def departement_de(commune: str) -> str:
    """Code département d'un code commune INSEE (5 caractères, Corse et outre-mer compris).

    Les arrondissements de Paris, Lyon et Marseille (75101, 69381, 13201…) suivent la même
    règle que les communes.
    """
    commune = commune.strip().zfill(5)
    if len(commune) != 5:
        raise FichierIllisible(f"Code commune invalide : {commune!r}")
    if commune.startswith("97"):
        return commune[:3]
    return commune[:2]


@dataclass(frozen=True)
class Agregat:
    valeur: Decimal
    communes: int  # communes ayant contribué
    sans_poids: int = 0  # communes ignorées faute de poids (moyenne pondérée seulement)


def sommer(valeurs: Iterable[tuple[str, Decimal]]) -> dict[str, Agregat]:
    """Somme par département de valeurs communales."""
    totaux: dict[str, Decimal] = defaultdict(Decimal)
    nombres: dict[str, int] = defaultdict(int)
    for commune, valeur in valeurs:
        dep = departement_de(commune)
        totaux[dep] += valeur
        nombres[dep] += 1
    return {dep: Agregat(totaux[dep], nombres[dep]) for dep in totaux}


def moyenne_ponderee(
    valeurs: Iterable[tuple[str, Decimal]],
    poids: Mapping[str, Decimal],
    groupe: Callable[[str], str | None] = departement_de,
) -> dict[str, Agregat]:
    """Moyenne par département de valeurs communales, pondérée par le poids de chaque commune.

    `groupe` change le regroupement (région, France…) : il reçoit le code commune et
    renvoie le code du groupe, ou None pour laisser la commune de côté.
    Une commune sans poids (ou de poids nul) est ignorée et comptée dans « sans_poids ».
    """
    if not poids:
        raise FichierIllisible("Poids communaux absents : importer d'abord le recensement communal")
    sommes: dict[str, Decimal] = defaultdict(Decimal)
    poids_total: dict[str, Decimal] = defaultdict(Decimal)
    nombres: dict[str, int] = defaultdict(int)
    ignorees: dict[str, int] = defaultdict(int)
    for commune, valeur in valeurs:
        dep = groupe(commune)
        if dep is None:
            continue
        p = poids.get(commune.strip().zfill(5))
        if not p:
            ignorees[dep] += 1
            continue
        sommes[dep] += valeur * p
        poids_total[dep] += p
        nombres[dep] += 1
    return {
        dep: Agregat(sommes[dep] / poids_total[dep], nombres[dep], ignorees.get(dep, 0))
        for dep in sommes
    }
