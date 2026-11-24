"""Portrait des élus (Répertoire national des élus, ministère de l'Intérieur), rubrique VOTES.

Dossier de conception de l'appli « Que pensent et votent les Français ? », étapes 2, 5 et 6.

Le Répertoire national des élus est publié sur data.gouv.fr, un fichier CSV par mandat,
republié à une nouvelle adresse à chaque mise à jour : on retrouve chaque fichier par son
titre dans l'API data.gouv.fr. Quatre mandats sont retenus : maires, conseillers
départementaux, députés, sénateurs.

On compte les élus en fonction à la date du fichier, par territoire : ensemble, par sexe,
par tranche d'âge (âge à la date du fichier) et par groupe socioprofessionnel (premier
chiffre de la catégorie déclarée, les mêmes huit groupes que la population dans la
rubrique « Qui sont les Français ? »), et l'âge médian. Les noms, prénoms et dates de
naissance ne quittent jamais le connecteur : seuls des comptes sont enregistrés.

Territoires :
- départements ; la Collectivité européenne d'Alsace (code ``6AE`` des conseillers
  départementaux) est répartie entre le Bas-Rhin et le Haut-Rhin par le code du canton ;
  Martinique et Guyane (collectivités uniques) sont rangées dans leur département ;
  quelques maires sans code de département sont rattachés à celui de leur commune ;
- ``HORS_DEP/ZZ`` : députés et sénateurs des Français de l'étranger ;
- ``HORS_DEP/COM`` : collectivités d'outre-mer ;
- France métropolitaine = départements métropolitains ; France = tout.

Paris, la Corse, la Martinique et la Guyane n'ont pas de conseil départemental (leurs
assemblées ont un autre statut) : ils n'ont pas de conseillers départementaux ici.

Contrôles propres (l'import est rejeté sinon) : colonnes attendues, sexe, date de
naissance et catégorie lisibles, territoire connu, chaque département attendu présent.
"""

import csv
import io
import re
import statistics
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs.elections import (
    DEPARTEMENTS,
    DEPARTEMENTS_METROPOLE,
)
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

JEU = "https://www.data.gouv.fr/api/1/datasets/5c34c4d1634f4173183a64f1/"


@dataclass(frozen=True)
class Mandat:
    code: str  # modalité de la dimension « mandat » (migration 032)
    indicateur: str
    titre: str  # titre de la ressource sur data.gouv.fr
    prefixe: str  # nom donné au fichier brut, suivi de sa date
    # Départements sans ce mandat (statut particulier).
    sans: frozenset[str] = frozenset()


MANDATS = (
    Mandat("MAIRE", "ELUS_MAIRES", "elus-maires-mai.csv", "elus-maires"),
    Mandat(
        "CONSEILLER_DEP",
        "ELUS_CONSEILLERS_DEP",
        "elus-conseillers-departementaux-cd.csv",
        "elus-conseillers-departementaux",
        sans=frozenset({"75", "2A", "2B", "972", "973"}),
    ),
    Mandat("DEPUTE", "ELUS_DEPUTES", "elus-deputes-dep.csv", "elus-deputes"),
    Mandat("SENATEUR", "ELUS_SENATEURS", "elus-senateurs-sen.csv", "elus-senateurs"),
)

# Premier chiffre de la catégorie socioprofessionnelle -> groupe (dimension « pcs »).
GROUPES = {
    "1": "AGRICULTEURS",
    "2": "ARTISANS_COMMERCANTS",
    "3": "CADRES",
    "4": "PROF_INTERMEDIAIRES",
    "5": "EMPLOYES",
    "6": "OUVRIERS",
    "7": "RETRAITES",
    "8": "AUTRES_SANS_ACTIVITE",
}
TRANCHES = ((18, 39), (40, 59), (60, 74), (75, None))
COLLECTIVITES = frozenset({"975", "977", "978", "986", "987", "988", "ZX"})
_NOM = re.compile(r"^(elus-[a-z-]+)-(\d{4}-\d{2}-\d{2})\.csv$")

DEPARTEMENT = "Code du département"
COLLECTIVITE = "Code de la collectivité à statut particulier"
CANTON = "Code du canton"
COMMUNE = "Code de la commune"
SEXE = "Code sexe"
NAISSANCE = "Date de naissance"
CATEGORIE = "Code de la catégorie socio-professionnelle"


def territoire(ligne: dict[str, str]) -> tuple[str, str]:
    """(niveau, code) du territoire d'un élu."""
    code = (ligne.get(DEPARTEMENT) or "").strip()
    if code == "6AE":  # Collectivité européenne d'Alsace : le canton dit le département
        code = (ligne.get(CANTON) or "")[:2]
    if not code:
        code = (ligne.get(COLLECTIVITE) or "").strip()
    if not code:  # quelques maires sans département : celui de leur commune
        commune = (ligne.get(COMMUNE) or "").strip()
        code = commune[:3] if commune.startswith("97") else commune[:2]
    if code in DEPARTEMENTS:
        return ("DEP", code)
    if code in COLLECTIVITES:
        return ("HORS_DEP", "COM")
    if code == "ZZ":
        return ("HORS_DEP", "ZZ")
    raise FichierIllisible(f"Territoire inconnu : département {code!r}")


def _territoires_agreges(code: tuple[str, str]) -> list[tuple[str, str]]:
    cibles = [code, ("FRANCE", "FR")]
    if code[0] == "DEP" and code[1] in DEPARTEMENTS_METROPOLE:
        cibles.append(("FRANCE", "FM"))
    return cibles


def age(naissance: date, jour: date) -> int:
    return jour.year - naissance.year - ((jour.month, jour.day) < (naissance.month, naissance.day))


def _tranche(annees: int) -> tuple[int, int | None]:
    for debut, fin in TRANCHES:
        if annees >= debut and (fin is None or annees <= fin):
            return (debut, fin)
    raise FichierIllisible(f"Élu de moins de 18 ans ({annees} ans)")


@dataclass
class _Comptes:
    total: int = 0
    sexes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tranches: dict[tuple[int, int | None], int] = field(default_factory=lambda: defaultdict(int))
    groupes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    ages: list[int] = field(default_factory=list)


def compter(texte: str, mandat: Mandat, jour: date) -> dict[tuple[str, str], _Comptes]:
    """Comptes par territoire, à partir du CSV du Répertoire."""
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
    manquantes = {SEXE, NAISSANCE, CATEGORIE, DEPARTEMENT} - set(lecteur.fieldnames or ())
    if manquantes:
        raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
    comptes: dict[tuple[str, str], _Comptes] = defaultdict(_Comptes)
    vus: set[str] = set()
    for ligne in lecteur:
        code = territoire(ligne)
        if code[0] == "DEP":
            vus.add(code[1])
        sexe = {"M": "H", "F": "F"}.get((ligne[SEXE] or "").strip())
        if sexe is None:
            raise FichierIllisible(f"Sexe illisible : {ligne[SEXE]!r}")
        try:
            annees = age(date.fromisoformat(ligne[NAISSANCE].strip()), jour)
        except ValueError as erreur:
            raise FichierIllisible(f"Date de naissance illisible : {erreur}") from erreur
        groupe = GROUPES.get((ligne[CATEGORIE] or "").strip()[:1])
        if groupe is None:
            raise FichierIllisible(f"Catégorie illisible : {ligne[CATEGORIE]!r}")
        tranche = _tranche(annees)
        for cible in _territoires_agreges(code):
            c = comptes[cible]
            c.total += 1
            c.sexes[sexe] += 1
            c.tranches[tranche] += 1
            c.groupes[groupe] += 1
            c.ages.append(annees)
    manquants = DEPARTEMENTS - mandat.sans - vus
    if manquants:
        raise FichierIllisible(
            f"{mandat.code} : départements absents ({', '.join(sorted(manquants))})"
        )
    return comptes


class Elus:
    source = "MI_RNE"
    niveaux_publies = frozenset({"FRANCE", "DEP", "HORS_DEP"})
    tolerance_sommes = 0.0
    lit_le_nom = True  # le mandat et la date viennent du nom du fichier
    # Départements tous présents : exigé (False pour un extrait de test).
    couverture = True

    def fichiers(self) -> list[Fichier]:
        jeu = telechargement.lire_json(JEU)
        ressources = jeu.get("resources", []) if isinstance(jeu, dict) else []
        fichiers = []
        for mandat in MANDATS:
            retenues = [r for r in ressources if r.get("title") == mandat.titre]
            if len(retenues) != 1:
                raise FichierIllisible(f"Ressource « {mandat.titre} » introuvable ou en double")
            r = retenues[0]
            jour = str(r.get("last_modified", ""))[:10]
            try:
                date.fromisoformat(jour)
            except ValueError as erreur:
                raise FichierIllisible(f"{mandat.titre} : date de mise à jour absente") from erreur
            fichiers.append(
                Fichier(url=r["url"], nom=f"{mandat.prefixe}-{jour}.csv", millesime=jour)
            )
        return fichiers

    def accepte(self, nom_fichier: str) -> bool:
        trouve = _NOM.match(nom_fichier)
        return bool(trouve) and any(m.prefixe == trouve[1] for m in MANDATS)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        trouve = _NOM.match(chemin.name)
        if not trouve:
            raise FichierIllisible(f"Nom de fichier inattendu : {chemin.name}")
        (mandat,) = [m for m in MANDATS if m.prefixe == trouve[1]]
        jour = date.fromisoformat(trouve[2])
        try:
            texte = chemin.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as erreur:
            raise FichierIllisible(f"CSV illisible : {erreur}") from erreur
        if not self.couverture:
            mandat = Mandat(mandat.code, mandat.indicateur, mandat.titre, mandat.prefixe,
                            sans=DEPARTEMENTS)  # fmt: skip
        mois = jour.replace(day=1)  # effectifs en fonction au mois de la mise à jour

        def ligne(indicateur, niveau, code, valeur, sexe="T", ages=(None, None), modalite=None):
            return Ligne(
                indicateur, niveau, code, mois, "MOIS", sexe, ages[0], ages[1], valeur,
                "DEFINITIF", modalite=modalite,
            )  # fmt: skip

        for (niveau, code), c in compter(texte, mandat, jour).items():
            yield ligne(mandat.indicateur, niveau, code, c.total)
            for sexe, n in c.sexes.items():
                yield ligne(mandat.indicateur, niveau, code, n, sexe=sexe)
            for tranche, n in c.tranches.items():
                yield ligne(mandat.indicateur, niveau, code, n, ages=tranche)
            for groupe, n in c.groupes.items():
                yield ligne(mandat.indicateur, niveau, code, n, modalite=("pcs", groupe))
            mediane = Decimal(str(statistics.median(c.ages))).quantize(Decimal("0.1"))
            yield ligne("AGE_MEDIAN_ELUS", niveau, code, mediane, modalite=("mandat", mandat.code))


ELUS = Elus()
