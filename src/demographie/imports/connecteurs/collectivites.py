"""Comptes des collectivités locales (DGFiP, data.economie.gouv.fr), par département.

Trois familles de jeux « comptes individuels », un jeu par année ou paire d'années :
départements (et collectivités territoriales uniques), communes, groupements à fiscalité
propre (intercommunalités). Montants en milliers d'euros. On ne télécharge pas les
dizaines de milliers de lignes des communes : l'API Opendatasoft les additionne par
département et par année (`group_by`), et on lit ce petit export JSON.

Dépenses retenues : charges de fonctionnement plus dépenses d'investissement, hors
remboursement du capital des emprunts (une dette qu'on rembourse n'est pas une dépense
nouvelle). Dette : encours au 31 décembre.

Codes particuliers des jeux : départements sur trois caractères (« 001 »), outre-mer en
« 101 » à « 106 ». La Collectivité européenne d'Alsace est publiée sous « 067 » (Bas-Rhin
et Haut-Rhin depuis 2021), la Collectivité de Corse sous « 02A » (depuis 2018) ; Paris est
une commune (son budget départemental est dans les communes).
"""

import json
import re
import urllib.parse
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
PREMIERE_ANNEE = 2016
OUTRE_MER = {"101": "971", "102": "972", "103": "973", "104": "974", "106": "976"}
MILLIER = Decimal(1000)  # milliers d'euros -> millions d'euros
# Code des jeux de groupements hors du code officiel géographique (quelques millions
# d'euros par an) : écarté plutôt que de faire rejeter tout le fichier.
IGNORES = frozenset({"161"})


def code_departement(code: str) -> str:
    """« 001 » -> « 01 », « 02A » -> « 2A », « 101 » -> « 971 »."""
    code = str(code).strip()
    if code in OUTRE_MER:
        return OUTRE_MER[code]
    return code[1:] if len(code) == 3 and code[0] == "0" else code


@dataclass(frozen=True)
class Famille:
    """Une famille de jeux : préfixe de l'identifiant, colonnes, et comment en tirer les
    dépenses (total et postes) et la dette."""

    nom: str  # « departements », « communes », « groupements »
    prefixe: str
    colonne_annee: str
    colonne_departement: str
    colonnes: tuple[str, ...]
    depenses: str  # indicateur
    dette: str  # indicateur
    # sommes -> (total des dépenses, {poste: montant}, dette), en milliers d'euros
    calcul: Callable[[dict[str, Decimal]], tuple[Decimal, dict[str, Decimal], Decimal]]


def _departements(s):
    fonctionnement = s["tcf"]
    investissement = s["tib"] - s["rce"]
    postes = {
        "PERSONNEL": s["chp"],
        "AIDES_SOCIALES": s["aid"],
        "HEBERGEMENT": s["fsh"],
        "AUTRES_FONCTIONNEMENT": fonctionnement - s["chp"] - s["aid"] - s["fsh"],
        "EQUIPEMENT": s["ded"],
        "AUTRES_INVESTISSEMENT": investissement - s["ded"],
    }
    return fonctionnement + investissement, postes, s["dba"]


def _communes(s):
    fonctionnement = s["charge"]
    investissement = s["depinv"] - s["remb"]
    postes = {
        "PERSONNEL": s["perso"],
        "ACHATS": s["achat"],
        "AUTRES_FONCTIONNEMENT": fonctionnement - s["perso"] - s["achat"],
        "EQUIPEMENT": s["equip"],
        "AUTRES_INVESTISSEMENT": investissement - s["equip"],
    }
    return fonctionnement + investissement, postes, s["dette"]


def _groupements(s):
    return s["cftot"] + s["eitot"] - s["edettot"], {}, s["entot"]


DEPARTEMENTS = Famille(
    "departements",
    "comptes-individuels-des-departements-et-des-collectivites-territoriales-uniques-"
    "fichier-global-",
    "exer", "dep", ("tcf", "chp", "aid", "fsh", "tib", "rce", "ded", "dba"),
    "DEPENSES_DEPARTEMENT", "DETTE_DEPARTEMENT", _departements,
)  # fmt: skip
COMMUNES = Famille(
    "communes",
    "comptes-individuels-des-communes-fichier-global-",
    "an", "dep", ("charge", "perso", "achat", "depinv", "remb", "equip", "dette"),
    "DEPENSES_COMMUNES", "DETTE_COMMUNES", _communes,
)  # fmt: skip
GROUPEMENTS = Famille(
    "groupements",
    "comptes-individuels-des-groupements-a-fiscalite-propre-fichier-global-",
    "exer", "ndept", ("cftot", "eitot", "edettot", "entot"),
    "DEPENSES_INTERCO", "DETTE_INTERCO", _groupements,
)  # fmt: skip


@dataclass(frozen=True)
class ComptesLocaux:
    famille: Famille
    source: str = "DGFIP_COMPTES_LOCAUX"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "DEP"})
    lit_le_nom: bool = True
    departements_absents: frozenset[str] = field(default_factory=frozenset)

    def accepte(self, nom_fichier: str) -> bool:
        motif = rf"comptes-{self.famille.nom}-\d{{4}}(-\d{{4}})?\.json"
        return re.fullmatch(motif, nom_fichier) is not None

    def _requete(self, jeu: str) -> str:
        f = self.famille
        sommes = ", ".join(f"sum({c}) as {c}" for c in f.colonnes)
        parametres = {
            "select": f"{f.colonne_annee} as annee, {f.colonne_departement} as dep, {sommes}",
            "group_by": f"{f.colonne_annee}, {f.colonne_departement}",
        }
        return f"{API}/{jeu}/exports/json?{urllib.parse.urlencode(parametres)}"

    def fichiers(self) -> list[Fichier]:
        requete = urllib.parse.urlencode(
            {
                "where": f'search("{self.famille.prefixe.rstrip("-")}")',
                "limit": 100,
                "select": "dataset_id",
            }  # fmt: skip
        )
        reponse = json.loads(telechargement.lire_page(f"{API}?{requete}"))
        motif = re.compile(re.escape(self.famille.prefixe) + r"(\d{4})(?:-(\d{4}))?$")
        trouves = []
        for jeu in reponse.get("results", []):
            m = motif.match(str(jeu.get("dataset_id", "")))
            if m and int(m[1]) >= PREMIERE_ANNEE:
                annees = m[1] + (f"-{m[2]}" if m[2] else "")
                trouves.append(
                    Fichier(
                        url=self._requete(jeu["dataset_id"]),
                        nom=f"comptes-{self.famille.nom}-{annees}.json",
                        millesime=annees,
                    )
                )
        if not trouves:
            raise FichierIllisible(f"Aucun jeu « comptes individuels des {self.famille.nom} »")
        return sorted(trouves, key=lambda f: f.nom)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        f = self.famille
        try:
            lignes = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not isinstance(lignes, list) or not lignes:
            raise FichierIllisible("Aucune ligne")
        absentes = {"annee", "dep", *f.colonnes} - set(lignes[0])
        if absentes:
            raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(absentes))}")
        france: dict[tuple, Decimal] = defaultdict(Decimal)
        vues: set[tuple[int, str]] = set()
        for ligne in lignes:
            if str(ligne["dep"]).strip() in IGNORES:
                continue
            annee, dep = int(ligne["annee"]), code_departement(ligne["dep"])
            if (annee, dep) in vues:
                raise FichierIllisible(f"Département en double : {dep} {annee}")
            vues.add((annee, dep))
            sommes = {c: Decimal(str(ligne[c] or 0)) for c in f.colonnes}
            total, postes, dette = f.calcul(sommes)
            periode = date(annee, 1, 1)
            valeurs = [(f.depenses, None, total), (f.dette, None, dette)]
            valeurs += [(f.depenses, ("poste_local", p), v) for p, v in postes.items()]
            for indicateur, modalite, montant in valeurs:
                montant = round(montant / MILLIER, 3)
                france[(indicateur, modalite, periode)] += montant
                yield Ligne(indicateur, "DEP", dep, periode, "ANNEE", "T", None, None,
                            montant, "DEFINITIF", modalite)  # fmt: skip
        for (indicateur, modalite, periode), montant in sorted(france.items(), key=str):
            yield Ligne(indicateur, "FRANCE", "FR", periode, "ANNEE", "T", None, None,
                        montant, "DEFINITIF", modalite)  # fmt: skip


COMPTES_DEPARTEMENTS = ComptesLocaux(DEPARTEMENTS)
COMPTES_COMMUNES = ComptesLocaux(COMMUNES)
COMPTES_GROUPEMENTS = ComptesLocaux(GROUPEMENTS)
