"""Appli « Comment travaillent les Français ? », PR T5 : télétravail et accidents du travail.

Télétravail : enquête Emploi de l'INSEE, résultats annuels (jeu Melodi « DD_EEC_ANNUEL »,
mesure PTREMOTE) : part des personnes en emploi ayant télétravaillé au moins un jour par
semaine pendant les quatre dernières semaines travaillées, pour la France (hors Mayotte),
au total et par grande catégorie socioprofessionnelle. Un seul millésime est en ligne : il
change chaque année. L'enquête ne descend pas au département.

Accidents du travail : Assurance maladie, risques professionnels, « sinistralité par
région administrative » (portail data.ameli.fr, Opendatasoft, sans compte) : accidents
du travail, accidents de trajet et maladies professionnelles reconnus, avec le nombre de
salariés du régime général, chaque année depuis 2005, par région et pour la France. Les
régions font exactement la somme de la France (contrôle des sommes du pipeline). Mayotte
est publiée à zéro salarié jusqu'en 2020 (années écartées), puis avec quelques accidents
seulement (3 pour 38 000 salariés en 2024) : ses nombres sont gardés pour les sommes, mais
pas son indice, qui ne veut rien dire. L'indice de fréquence (accidents pour 1 000
salariés) est recalculé à la lecture ; il est égal au chiffre publié.

Les grèves (journées non travaillées, DARES) et l'audience syndicale attendent une source
téléchargeable : le jeu ouvert des grèves ne contient plus que les années.

Dossier de conception de l'appli travail, étapes 2 et 5 (thèmes après le MVP).
"""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from demographie.imports import telechargement
from demographie.imports.connecteurs import fichier
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

UN_DIXIEME = Decimal("0.1")

# --- Télétravail (enquête Emploi) ---

MELODI = "https://api.insee.fr/melodi/data"
JEU_EEC = "DD_EEC_ANNUEL"
FILTRES_EEC = {"EEC_MEASURE": "PTREMOTE", "EMPSTA": "1_BIT"}
# Grandes catégories socioprofessionnelles (PCS 2020) -> modalité « pcs ». Les indépendants
# (10, 20, 21…) ne sont pas publiés ; les catégories fines sont ignorées.
PCS = {
    "_T": None,
    "30": "CADRES",
    "40": "PROF_INTERMEDIAIRES",
    "50": "EMPLOYES",
    "60": "OUVRIERS",
}


@dataclass(frozen=True)
class Teletravail:
    source: str = "INSEE_EEC"
    nom_fichier: str = f"{JEU_EEC}_PTREMOTE.json"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    # Pas de département : ni couverture départementale ni sommes à contrôler.
    controle_couverture: bool = False
    tolerance_sommes: float = 0.005

    def fichiers(self) -> list[Fichier]:
        requete = urlencode({**FILTRES_EEC, "maxResult": 1000})
        return [Fichier(url=f"{MELODI}/{JEU_EEC}?{requete}", nom=self.nom_fichier)]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            observations = json.loads(chemin.read_text(encoding="utf-8"))["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        lignes = []
        for obs in observations:
            dim = obs.get("dimensions") if isinstance(obs, dict) else None
            if not isinstance(dim, dict) or "TIME_PERIOD" not in dim:
                raise FichierIllisible(f"Observation illisible : {obs}")
            autres = {
                k: v
                for k, v in dim.items()
                if k not in ("TIME_PERIOD", "FREQ", "PCS", *FILTRES_EEC) and v != "_T"
            }
            if autres or any(dim.get(k) != v for k, v in FILTRES_EEC.items()):
                raise FichierIllisible(f"Dimensions inattendues : {dim}")
            pcs = dim.get("PCS", "_T")
            if pcs not in PCS:
                continue  # catégorie fine
            statut = (obs.get("attributes") or {}).get("OBS_STATUS", "A")
            valeur = (obs.get("measures") or {}).get("OBS_VALUE_NIVEAU", {}).get("value")
            if statut != "A" or valeur is None:
                continue  # sans objet ou non significatif
            try:
                part = Decimal(str(valeur)).quantize(UN_DIXIEME)
                annee = int(dim["TIME_PERIOD"])
            except (ArithmeticError, ValueError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            modalite = ("pcs", PCS[pcs]) if PCS[pcs] else None
            lignes.append(
                Ligne(
                    "PART_TELETRAVAIL",
                    "FRANCE",
                    "FR",
                    date(annee, 1, 1),
                    "ANNEE",
                    "T",
                    None,
                    None,
                    part,
                    "DEFINITIF",
                    modalite,
                )  # fmt: skip
            )
        if not any(x.modalite is None for x in lignes):
            raise FichierIllisible("Part du télétravail de l'ensemble absente")
        yield from sorted(lignes, key=lambda x: (x.periode, x.modalite or ("", "")))


# --- Accidents du travail (Assurance maladie) ---

AMELI = "https://data.ameli.fr/api/explore/v2.1/catalog/datasets"
JEU_AT = "sinistralite-par-region-administrative"
COLONNES_AT = frozenset({"annee", "code_region_admin", "risque", "nb_sinistres_int", "nb_salaries"})
RISQUES = {
    "Accidents du travail": "ACCIDENTS_TRAVAIL",
    "Accidents de trajet": "ACCIDENTS_TRAJET",
    "Maladies professionnelles": "MALADIES_PROFESSIONNELLES",
    "Tous risques confondus": None,  # somme des trois : pas retenue
}
FRANCE_AT = "99"
MAYOTTE = "06"


@dataclass(frozen=True)
class AccidentsTravail:
    source: str = "CNAM_RISQUES_PRO"
    nom_fichier: str = f"{JEU_AT}.csv"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG"})
    controle_couverture: bool = False
    # Les régions font exactement la somme de la France.
    tolerance_sommes: float = 0.001

    def fichiers(self) -> list[Fichier]:
        meta = telechargement.lire_json(f"{AMELI}/{JEU_AT}")
        metas = meta.get("metas", {}) if isinstance(meta, dict) else {}
        modifie = metas.get("default", {}).get("modified")
        requete = urlencode({"delimiter": ";", "order_by": "annee,code_region_admin,risque"})
        return [
            Fichier(
                url=f"{AMELI}/{JEU_AT}/exports/csv?{requete}",
                nom=self.nom_fichier,
                millesime=str(modifie)[:10] if modifie else None,
            )
        ]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        fmt = fichier.FormatCSV(encodage="utf-8-sig", separateur=";", decimale=".")
        indices: list[Ligne] = []
        for brut in fichier.lire_csv(chemin, fmt, COLONNES_AT):
            risque = brut["risque"]
            if risque not in RISQUES:
                raise FichierIllisible(f"Risque inattendu : {risque}")
            code = brut["code_region_admin"]
            if not re.fullmatch(r"\d{2}", code) or not re.fullmatch(r"\d{4}", brut["annee"]):
                raise FichierIllisible(f"Ligne illisible : {brut}")
            if RISQUES[risque] is None:
                continue
            sinistres = fichier.nombre(brut["nb_sinistres_int"], ".")
            salaries = fichier.nombre(brut["nb_salaries"], ".")
            if sinistres is None or salaries is None:
                raise FichierIllisible(f"{code} {brut['annee']} {risque} : valeur vide")
            if not salaries:
                continue  # Mayotte avant 2021
            avec_indice = code != MAYOTTE
            niveau, code = ("FRANCE", "FR") if code == FRANCE_AT else ("REG", code)
            periode = date(int(brut["annee"]), 1, 1)
            yield Ligne(RISQUES[risque], niveau, code, periode, "ANNEE", "T", None, None,
                        int(sinistres), "DEFINITIF")  # fmt: skip
            if RISQUES[risque] == "ACCIDENTS_TRAVAIL" and avec_indice:
                indice = (1000 * sinistres / salaries).quantize(UN_DIXIEME)
                indices.append(
                    Ligne(
                        "INDICE_FREQUENCE_AT",
                        niveau,
                        code,
                        periode,
                        "ANNEE",
                        "T",
                        None,
                        None,
                        indice,
                        "DEFINITIF",
                    )  # fmt: skip
                )
        yield from indices


TELETRAVAIL = Teletravail()
ACCIDENTS_TRAVAIL = AccidentsTravail()
