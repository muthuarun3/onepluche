"""Énergie des ménages (dossier de conception de l'appli 2, étape 6).

- Agence ORE : consommation annuelle d'électricité et de gaz du secteur résidentiel et
  nombre de points de livraison, par département et par gestionnaire de réseau (API
  data-fair). Les gestionnaires d'un même département sont additionnés.
- ADEME : diagnostics de performance énergétique (DPE) des logements existants, comptés
  par l'API (values_agg) par département, étiquette et année d'établissement.
- INSEE : indice des prix à la consommation (base 2025, France), par poste.

Les sources sont interrogées par API puis enregistrées dans un fichier JSON trié, archivé
comme brut, comme pour Melodi.
"""

import json
import re
import tempfile
import urllib.parse
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from defusedxml.ElementTree import iterparse

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

DROM = frozenset({"971", "972", "973", "974", "976"})


def _ecrire_json(dossier: Path, contenu: dict) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=dossier, suffix=".part", delete=False, encoding="utf-8"
    ) as sortie:
        json.dump(contenu, sortie, sort_keys=True)
    return Path(sortie.name)


def _lire_json(chemin: Path) -> dict:
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except ValueError as erreur:
        raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
    if not isinstance(contenu, dict):
        raise FichierIllisible("JSON inattendu")
    return contenu


def _sommes_territoriales(
    par_departement: dict[str, Decimal | int],
    referentiel: Referentiel,
    attendus: frozenset[str],
) -> dict[tuple[str, str], Decimal | int]:
    """Département, puis région et France quand tous leurs départements sont présents.

    `attendus` : départements que la source couvre normalement ; une région ou la France
    à laquelle il en manque un n'est pas publiée (sa somme serait trop basse).
    """
    resultat: dict[tuple[str, str], Decimal | int] = {
        ("DEP", d): v for d, v in par_departement.items()
    }
    presents = set(par_departement)
    regions: dict[str, list[str]] = defaultdict(list)
    for departement, region in referentiel.region_du_departement.items():
        if departement in attendus:
            regions[region].append(departement)
    for region, departements in regions.items():
        if set(departements) <= presents:
            resultat[("REG", region)] = sum(par_departement[d] for d in departements)
    if attendus and attendus <= presents:
        resultat[("FRANCE", "FR")] = sum(par_departement[d] for d in attendus)
        resultat[("FRANCE", "FM")] = sum(par_departement[d] for d in attendus - DROM)
    return resultat


# --- Agence ORE -------------------------------------------------------------------------

ORE = (
    "https://opendata.agenceore.fr/data-fair/api/v1/datasets/"
    "consommation-annuelle-d-electricite-et-gaz-par-departement/lines"
)
_ORE_CHAMPS = (
    "operateur,filiere,annee,code_departement,code_grand_secteur,nb_sites,conso_totale_mwh"
)


@dataclass(frozen=True)
class ConsommationOre:
    filiere: str  # « Electricité » ou « Gaz », valeur de la source
    suffixe: str
    indicateur_conso: str
    indicateur_points: str
    # Départements sans réseau de cette énergie (gaz : Corse, Lozère, outre-mer).
    departements_absents: frozenset[str] = frozenset()
    source: str = "ORE_CONSO"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True

    @property
    def nom_fichier(self) -> str:
        return f"ore-residentiel-{self.suffixe}.json"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=ORE, nom=self.nom_fichier)]

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        parametres = {
            "size": 10000,
            "select": _ORE_CHAMPS,
            "qs": f'code_grand_secteur:RESIDENTIEL AND filiere:"{self.filiere}"',
        }
        reponse = telechargement.lire_json(f"{ORE}?{urllib.parse.urlencode(parametres)}")
        if not isinstance(reponse, dict) or "results" not in reponse:
            raise FichierIllisible("Réponse inattendue de l'Agence ORE")
        lignes = reponse["results"]
        if reponse.get("total") != len(lignes):
            raise FichierIllisible(f"Réponse incomplète : {len(lignes)} / {reponse.get('total')}")
        for ligne in lignes:
            ligne.pop("_score", None)
        lignes.sort(key=lambda x: json.dumps(x, sort_keys=True))
        return _ecrire_json(dossier, {"filiere": self.filiere, "lignes": lignes})

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        lignes = _lire_json(chemin).get("lignes") or []
        if not lignes:
            raise FichierIllisible("Aucune ligne")
        conso: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        points: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for ligne in lignes:
            if ligne.get("filiere") != self.filiere or ligne.get("code_grand_secteur") != (
                "RESIDENTIEL"
            ):
                raise FichierIllisible(f"Ligne inattendue : {ligne}")
            if ligne.get("nb_sites") is None or ligne.get("conso_totale_mwh") is None:
                continue  # petit gestionnaire sous secret statistique
            try:
                annee = int(ligne["annee"])
                departement = str(ligne["code_departement"])
                conso[annee][departement] += Decimal(str(ligne["conso_totale_mwh"]))
                points[annee][departement] += int(ligne["nb_sites"])
            except (KeyError, TypeError, ValueError, InvalidOperation) as erreur:
                raise FichierIllisible(f"Ligne illisible : {ligne}") from erreur
        attendus = (
            frozenset(code for niveau, code in referentiel.identifiants if niveau == "DEP")
            - self.departements_absents
        )
        for annee in sorted(conso):
            for indicateur, valeurs in (
                (self.indicateur_conso, {d: round(v) for d, v in conso[annee].items()}),
                (self.indicateur_points, dict(points[annee])),
            ):
                for (niveau, code), valeur in sorted(
                    _sommes_territoriales(valeurs, referentiel, attendus).items()
                ):
                    yield Ligne(indicateur, niveau, code, date(annee, 1, 1), "ANNEE", "T",
                                None, None, valeur, "DEFINITIF")  # fmt: skip


ELECTRICITE = ConsommationOre(
    filiere="Electricité",
    suffixe="electricite",
    indicateur_conso="CONSO_ELEC_RESID",
    indicateur_points="POINTS_ELEC_RESID",
)
GAZ = ConsommationOre(
    filiere="Gaz",
    suffixe="gaz",
    indicateur_conso="CONSO_GAZ_RESID",
    indicateur_points="POINTS_GAZ_RESID",
    departements_absents=frozenset({"2A", "2B", "48"}) | DROM,
)


# --- DPE de l'ADEME ---------------------------------------------------------------------

DPE = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/values_agg"
PREMIERE_ANNEE_DPE = 2021  # nouveau DPE, depuis juillet 2021
ETIQUETTES = ("A", "B", "C", "D", "E", "F", "G")
# Codes de la source hors référentiel (collectivités d'outre-mer) : 0,5 % au plus.
PART_HORS_REFERENTIEL_MAX = 0.005


@dataclass(frozen=True)
class DiagnosticsAdeme:
    source: str = "ADEME_DPE"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True
    nom_fichier: str = "ademe-dpe-logements-existants.json"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=DPE, nom=self.nom_fichier)]

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        comptes = {}
        for annee in range(PREMIERE_ANNEE_DPE, date.today().year + 1):
            parametres = {
                "field": "code_departement_ban,etiquette_dpe",
                "agg_size": "200,10",
                "size": 0,
                "qs": f"date_etablissement_dpe:[{annee}-01-01 TO {annee}-12-31]",
            }
            reponse = telechargement.lire_json(f"{DPE}?{urllib.parse.urlencode(parametres)}")
            if not isinstance(reponse, dict) or reponse.get("total_other"):
                raise FichierIllisible(f"Agrégat DPE {annee} inattendu ou tronqué")
            comptes[str(annee)] = {
                a["value"]: {e["value"]: e["total"] for e in a["aggs"]} for a in reponse["aggs"]
            }
        return _ecrire_json(dossier, {"comptes": comptes, "jusqu_au": date.today().isoformat()})

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        contenu = _lire_json(chemin)
        try:
            comptes = contenu["comptes"]
            extrait_le = date.fromisoformat(contenu["jusqu_au"])
        except (KeyError, TypeError, ValueError) as erreur:
            raise FichierIllisible(f"Fichier DPE incomplet : {erreur}") from erreur
        connus = {code for niveau, code in referentiel.identifiants if niveau == "DEP"}
        attendus = frozenset(connus)
        for annee_texte, par_departement in sorted(comptes.items()):
            annee = int(annee_texte)
            # L'année en cours (et 2021, commencée en juillet) n'est pas complète.
            statut = "DEFINITIF" if annee < extrait_le.year and annee > 2021 else "PROVISOIRE"
            total = sum(sum(e.values()) for e in par_departement.values())
            hors = sum(sum(e.values()) for d, e in par_departement.items() if d not in connus)
            if total == 0 or hors > PART_HORS_REFERENTIEL_MAX * total:
                raise FichierIllisible(f"DPE {annee} : {hors} sur {total} hors référentiel")
            par_etiquette: dict[str | None, dict[str, int]] = defaultdict(dict)
            for departement, etiquettes in par_departement.items():
                if departement not in connus:
                    continue
                inconnues = set(etiquettes) - set(ETIQUETTES)
                if inconnues:
                    raise FichierIllisible(f"Étiquettes inattendues : {inconnues}")
                par_etiquette[None][departement] = sum(etiquettes.values())
                for etiquette, nombre in etiquettes.items():
                    par_etiquette[etiquette][departement] = nombre
            for etiquette, valeurs in par_etiquette.items():
                for (niveau, code), valeur in sorted(
                    _sommes_territoriales(valeurs, referentiel, attendus).items()
                ):
                    yield Ligne("DPE_ETABLIS", niveau, code, date(annee, 1, 1), "ANNEE", "T",
                                None, None, valeur, statut,
                                ("etiquette_dpe", etiquette) if etiquette else None)  # fmt: skip


# --- Indice des prix à la consommation --------------------------------------------------

IPC = "https://api.insee.fr/series/BDM/data/SERIES_BDM/"
# Base 2025, ensemble des ménages, France. IDBANK -> poste (None : ensemble).
POSTES_IPC = {
    "011814630": None,
    "011813864": "ENERGIE",
    "011815807": "ELECTRICITE",
    "011815822": "GAZ",
    "011815633": "LOYERS",
    "011816281": "SANTE",
}
_MOIS = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True)
class PrixConsommation:
    source: str = "INSEE_IPC"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    nom_fichier: str = "ipc-base-2025.xml"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=IPC + "+".join(POSTES_IPC), nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        vues: Counter[str] = Counter()
        try:
            for _evenement, element in iterparse(str(chemin), events=("end",)):
                if not element.tag.endswith("Series"):
                    continue
                attributs = element.attrib
                idbank = attributs.get("IDBANK", "")
                if idbank not in POSTES_IPC or attributs.get("FREQ") != "M":
                    raise FichierIllisible(f"Série inattendue : {idbank}")
                if "Base 2025" not in attributs.get("TITLE_FR", ""):
                    raise FichierIllisible(f"Série {idbank} d'une autre base que 2025")
                poste = POSTES_IPC[idbank]
                for obs in element:
                    mois = _MOIS.match(obs.attrib.get("TIME_PERIOD", ""))
                    if not mois:
                        raise FichierIllisible(f"Période inattendue : {obs.attrib}")
                    valeur = Decimal(obs.attrib["OBS_VALUE"])
                    statut = "DEFINITIF" if obs.attrib.get("OBS_QUAL") == "DEF" else "PROVISOIRE"
                    vues[idbank] += 1
                    yield Ligne("IPC", "FRANCE", "FR", date(int(mois[1]), int(mois[2]), 1),
                                "MOIS", "T", None, None, valeur, statut,
                                ("poste_ipc", poste) if poste else None)  # fmt: skip
                element.clear()
        except FichierIllisible:
            raise
        except Exception as erreur:  # XML mal formé ou interdit, valeur illisible
            raise FichierIllisible(f"XML illisible : {erreur}") from erreur
        manquantes = set(POSTES_IPC) - set(vues)
        if manquantes:
            raise FichierIllisible(f"Séries absentes : {', '.join(sorted(manquantes))}")


DIAGNOSTICS = DiagnosticsAdeme()
PRIX = PrixConsommation()
