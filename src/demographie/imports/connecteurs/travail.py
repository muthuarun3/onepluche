"""Appli « Comment travaillent les Français ? », PR T1 : séries de la BDM de l'INSEE.

Cinq jeux (« dataflows ») de la BDM, chacun filtré par une clé SDMX pour ne rapatrier que
les séries utiles : sans clé, l'INSEE refuse les jeux d'emploi (« réponse trop
volumineuse »). Une balise Series par territoire et par ventilation (sexe, âge, secteur,
type d'entreprise), une balise Obs par période. Les parts (intérim, indépendants) sont
calculées à la lecture, dans le même fichier que leurs deux termes.

Dossier de conception de l'appli travail, étapes 5 à 7.
"""

import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from defusedxml.ElementTree import iterparse

from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://api.insee.fr/series/BDM/data"
PERIODES = {
    "A": (re.compile(r"^(\d{4})$"), "ANNEE"),
    "T": (re.compile(r"^(\d{4})-Q([1-4])$"), "TRIMESTRE"),
    "M": (re.compile(r"^(\d{4})-(\d{2})$"), "MOIS"),
}
# Zones de la BDM hors départements et régions. None : zone ignorée (agrégat sans
# équivalent dans le référentiel, comme « France hors Île-de-France »).
ZONES = {
    "FM": ("FRANCE", "FM"),  # France métropolitaine
    "FE": ("FRANCE", "FR"),  # France entière
    "FR-D976": ("FRANCE", "FR"),  # France hors Mayotte, seul total national publié
    "DOM": None,
    "D99": None,  # total des départements d'outre-mer
    "F_H_IDF": None,
}
# Écart admis entre un total et la somme de ses parties : les séries corrigées des
# variations saisonnières ne s'additionnent pas exactement.
TOLERANCE_SOMMES = Decimal("0.01")

# (sexe, age_min, age_max, modalité) d'une série, ou None si la série est ignorée.
Ventilation = tuple[str, int | None, int | None, tuple[str, str] | None]


@dataclass(frozen=True)
class JeuBdmTravail:
    source: str
    jeu: str
    # Clé SDMX : une valeur (ou « a+b ») par dimension, dans l'ordre du jeu, vide = toutes.
    cle: str
    indicateur: str
    frequence: str
    # Attributs de la série -> ventilation ; KeyError ou None : série inattendue.
    ventilation: Callable[[dict[str, str]], Ventilation | None]
    niveaux_publies: frozenset[str] = field(default=frozenset({"FRANCE", "REG", "DEP"}))
    # Part calculée : (indicateur, modalité du numérateur, modalité du dénominateur).
    part: tuple[str, tuple[str, str] | None, tuple[str, str] | None] | None = None
    # Contrôle de somme : modalités qui doivent faire le total (modalité None).
    parties: frozenset[tuple[str, str]] = frozenset()
    # Contrôles du pipeline : France comparée à la somme des départements, départements
    # attendus à la dernière période (Mayotte absente de la plupart de ces séries).
    tolerance_sommes: float = 0.01
    # Première année gardée : avant, la France ne fait pas la somme des départements.
    debut: int | None = None
    controle_couverture: bool = True
    departements_absents: frozenset[str] = frozenset({"976"})

    @property
    def nom_fichier(self) -> str:
        return f"{self.jeu}.xml"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=f"{API}/{self.jeu}/{self.cle}", nom=self.nom_fichier)]

    def _territoires(self, zone: str, referentiel: Referentiel) -> list[tuple[str, str]]:
        if zone in ZONES:
            return [ZONES[zone]] if ZONES[zone] else []
        if zone.startswith("R"):
            return [("REG", zone[1:])]
        if zone.startswith("D"):
            departement = zone[1:]
            region = referentiel.region_mono_departementale(departement)
            regions = [("REG", region)] if region and "REG" in self.niveaux_publies else []
            return [("DEP", departement)] + regions
        # Zone inconnue : transmise telle quelle, le pipeline rejettera le fichier.
        return [("DEP", zone)]

    def _periode(self, texte: str) -> date:
        motif, _type = PERIODES[self.frequence]
        trouve = motif.match(texte)
        if not trouve:
            raise FichierIllisible(f"Période inattendue : {texte}")
        annee = int(trouve[1])
        if self.frequence == "A":
            return date(annee, 1, 1)
        if self.frequence == "T":
            return date(annee, 3 * int(trouve[2]) - 2, 1)
        return date(annee, int(trouve[2]), 1)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        lignes = list(self._lire_series(chemin, referentiel))
        # Les régions d'outre-mer reprises de leur département ne doublonnent pas une
        # région publiée par la BDM.
        vues: set[tuple] = set()
        uniques = []
        for ligne in lignes:
            cle = (ligne.niveau, ligne.code, ligne.periode, ligne.sexe, ligne.age_min,
                   ligne.age_max, ligne.modalite)  # fmt: skip
            if cle in vues:
                if ligne.niveau == "REG":
                    continue
                raise FichierIllisible(f"Valeur en double : {cle}")
            vues.add(cle)
            uniques.append(ligne)
        self._controler_sommes(uniques)
        yield from uniques
        if self.part:
            yield from self._parts(uniques)

    def _lire_series(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        series = 0
        type_periode = PERIODES[self.frequence][1]
        try:
            for _evenement, element in iterparse(str(chemin), events=("end",)):
                if not element.tag.endswith("}Series") and element.tag != "Series":
                    continue
                attributs = dict(element.attrib)
                if (
                    attributs.get("FREQ") != self.frequence
                    or attributs.get("UNIT_MULT", "0") != "0"
                ):
                    raise FichierIllisible(f"Série inattendue : {attributs.get('IDBANK')}")
                try:
                    ventilation = self.ventilation(attributs)
                except KeyError as erreur:
                    raise FichierIllisible(
                        f"Série inattendue : {attributs.get('IDBANK')} ({erreur})"
                    ) from erreur
                series += 1
                territoires = self._territoires(attributs.get("REF_AREA", ""), referentiel)
                if ventilation is None or not territoires:
                    element.clear()
                    continue
                sexe, age_min, age_max, modalite = ventilation
                for obs in element:
                    try:
                        valeur = Decimal(obs.attrib["OBS_VALUE"])
                    except (KeyError, InvalidOperation) as erreur:
                        raise FichierIllisible(f"Valeur illisible : {obs.attrib}") from erreur
                    periode = self._periode(obs.attrib.get("TIME_PERIOD", ""))
                    if self.debut and periode.year < self.debut:
                        continue
                    statut = "DEFINITIF" if obs.attrib.get("OBS_STATUS") == "A" else "PROVISOIRE"
                    for niveau, code in territoires:
                        yield Ligne(self.indicateur, niveau, code, periode, type_periode,
                                    sexe, age_min, age_max, valeur, statut, modalite)  # fmt: skip
                element.clear()
        except FichierIllisible:
            raise
        except Exception as erreur:  # XML mal formé ou interdit (entités, DTD)
            raise FichierIllisible(f"XML illisible : {erreur}") from erreur
        if series == 0:
            raise FichierIllisible("Aucune série dans le fichier")

    def _controler_sommes(self, lignes: list[Ligne]) -> None:
        if not self.parties:
            return
        totaux: dict[tuple, Decimal] = {}
        sommes: dict[tuple, Decimal] = defaultdict(Decimal)
        nombres: dict[tuple, int] = defaultdict(int)
        for ligne in lignes:
            cle = (ligne.niveau, ligne.code, ligne.periode)
            if ligne.modalite is None:
                totaux[cle] = Decimal(ligne.valeur)
            elif ligne.modalite in self.parties:
                sommes[cle] += Decimal(ligne.valeur)
                nombres[cle] += 1
        for cle, total in totaux.items():
            if nombres[cle] != len(self.parties):
                continue  # partie manquante pour cette période (série commencée plus tard)
            if abs(sommes[cle] - total) > TOLERANCE_SOMMES * total:
                raise FichierIllisible(
                    f"{self.indicateur} {cle} : somme des parties {sommes[cle]} ≠ total {total}"
                )

    def _parts(self, lignes: list[Ligne]) -> Iterator[Ligne]:
        indicateur, numerateur, denominateur = self.part
        valeurs = {
            (x.niveau, x.code, x.periode, x.modalite): x
            for x in lignes
            if x.sexe == "T" and x.age_min is None
        }
        for (niveau, code, periode, modalite), ligne in valeurs.items():
            if modalite != numerateur:
                continue
            base = valeurs.get((niveau, code, periode, denominateur))
            if base is None or base.valeur == 0:
                continue
            statut = "PROVISOIRE" if "PROVISOIRE" in (ligne.statut, base.statut) else "DEFINITIF"
            valeur = round(100 * Decimal(ligne.valeur) / Decimal(base.valeur), 1)
            yield Ligne(indicateur, niveau, code, periode, ligne.periode_type, "T", None, None,
                        valeur, statut)  # fmt: skip


# --- Ventilations ------------------------------------------------------------------------

_SEXES = {"0": "T", "1": "H", "2": "F"}
_AGES = {"00-": (None, None), "15-24": (15, 24), "25-49": (25, 49), "50-": (50, None)}
_SECTEURS = {
    "ENS-SAL": None,
    "A5-AZ": ("secteur", "AGRICULTURE"),
    "A5-BE": ("secteur", "INDUSTRIE"),
    "A5-FZ": ("secteur", "CONSTRUCTION"),
    "A5-GU": ("secteur", "COMMERCE_SERVICES"),
    "A5-OQ": ("secteur", "ADMIN_ENSEIGNEMENT_SANTE"),
    "78-20Z": ("secteur", "INTERIM"),
}
_STATUTS = {
    "TOT": None,
    "SAL": ("statut_emploi", "SALARIE"),
    "NSAL": ("statut_emploi", "NON_SALARIE"),
}
_TYPES_ENTREPRISE = {"TYPE-ENT_TOTAL": None, "TYPE-ENT_AE": ("type_entreprise", "MICRO")}


def _chomage(a: dict[str, str]) -> Ventilation:
    age_min, age_max = _AGES[a["AGE"]]
    return (_SEXES[a["SEXE"]], age_min, age_max, None)


def _emploi_salarie(a: dict[str, str]) -> Ventilation:
    return ("T", None, None, _SECTEURS[a["NAF2"]])


def _emploi_total(a: dict[str, str]) -> Ventilation:
    return ("T", None, None, _STATUTS[a["CAT_POP_ACT"]])


def _creations(a: dict[str, str]) -> Ventilation:
    return ("T", None, None, _TYPES_ENTREPRISE[a["INDICATEUR"]])


def _defaillances(a: dict[str, str]) -> Ventilation:
    if a["ACTIVITE_CREAT_ENT"] != "ENS":
        raise KeyError(a["ACTIVITE_CREAT_ENT"])
    return ("T", None, None, None)


CHOMAGE_ANNUEL = JeuBdmTravail(
    source="INSEE_CHOM",
    jeu="TCRED-TRAVAIL-EMPLOI-TCHOMA-SA",
    # Taux localisés en métropole ; taux de l'enquête Emploi pour l'outre-mer et la France.
    cle="A.TAUX_CHOMAGE_LOCALISE_MOYENNE_ANNUELLE+TAUX_CHOMAGE_BIT_MOYENNE_ANNUELLE.TAUX......",
    indicateur="TAUX_CHOMAGE_ANNUEL",
    frequence="A",
    ventilation=_chomage,
)
EMPLOI_SALARIE = JeuBdmTravail(
    source="INSEE_EMPLOI",
    jeu="TCRED-EMPLOI-SALARIE-TRIM",
    cle="T.EMPLOI_SALARIE_TRIM.A5-AZ+A5-BE+A5-FZ+A5-GU+A5-OQ+78-20Z+ENS-SAL."
    "VALEUR_ABSOLUE..INDIVIDUS.CVS.FALSE",
    indicateur="EMPLOI_SALARIE",
    frequence="T",
    ventilation=_emploi_salarie,
    # Avant 2011 : ni outre-mer ni tertiaire non marchand par département.
    debut=2011,
    part=("PART_INTERIM", ("secteur", "INTERIM"), None),
    # L'intérim est compris dans le tertiaire marchand : il n'entre pas dans la somme.
    parties=frozenset(
        {
            ("secteur", c)
            for c in (
                "AGRICULTURE",
                "INDUSTRIE",
                "CONSTRUCTION",
                "COMMERCE_SERVICES",
                "ADMIN_ENSEIGNEMENT_SANTE",
            )
        }  # fmt: skip
    ),
)
EMPLOI_TOTAL = JeuBdmTravail(
    source="INSEE_EMPLOI",
    jeu="TCRED-EMPLOI-31-DECEMBRE-BASE-2018",
    cle="A.EMPLOI_31_DECEMBRE.TOT.VALEUR_ABSOLUE.SAL+NSAL+TOT.....",
    indicateur="EMPLOI_TOTAL",
    frequence="A",
    ventilation=_emploi_total,
    part=("PART_INDEPENDANTS", ("statut_emploi", "NON_SALARIE"), None),
    parties=frozenset({("statut_emploi", "SALARIE"), ("statut_emploi", "NON_SALARIE")}),
)
CREATIONS = JeuBdmTravail(
    source="INSEE_SIDE",
    jeu="CREATIONS-ENTREPRISES-METHODE-2022",
    cle="M.BDM.TYPE-ENT_TOTAL+TYPE-ENT_AE.ENS.VALEUR_ABSOLUE.SO..UNITE.BRUT.FALSE",
    indicateur="CREATIONS_ENTREPRISES",
    frequence="M",
    ventilation=_creations,
    departements_absents=frozenset(),
    # Ni régions ni France métropolitaine publiées pour les créations.
    niveaux_publies=frozenset({"FRANCE", "DEP"}),
)
DEFAILLANCES = JeuBdmTravail(
    source="INSEE_SIDE",
    jeu="DEFAILLANCES-ENTREPRISES",
    cle="T.BDM.NOMBRE_DEFAILLANCES.ENS.VALEUR_ABSOLUE..UNITE.BRUT.FALSE",
    indicateur="DEFAILLANCES_ENTREPRISES",
    frequence="T",
    ventilation=_defaillances,
    # Avant 1995, les départements ne couvrent qu'une partie des défaillances nationales.
    debut=1995,
)
