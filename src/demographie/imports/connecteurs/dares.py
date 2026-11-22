"""Appli « Comment travaillent les Français ? », PR T2 : demandeurs d'emploi (DARES).

Le jeu ouvert « dares_defm_stock_region_cvs_trim » de la DARES donne, chaque trimestre
depuis 1996, les inscrits à France Travail en fin de trimestre, corrigés des variations
saisonnières, par département (outre-mer compris, Mayotte absente), par région et pour la
France. On lit l'export CSV de l'API Opendatasoft, filtré sur les catégories A et ABC :
une ligne par trimestre, territoire, catégorie, sexe, tranche d'âge et ancienneté.

Les départements font la somme de leur région et de la France (écart de 0,03 % au plus,
dû aux arrondis à la dizaine) : le contrôle des sommes du pipeline le vérifie, avec une
tolérance de 1 % pour les tranches d'âge et les sexes des petits départements. La part
des inscrits depuis un an ou plus est calculée à la lecture.

Dossier de conception de l'appli travail, étapes 5 à 7 (et ajustements de la PR T2).
"""

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

JEU = "dares_defm_stock_region_cvs_trim"
API = "https://data.dares.travail-emploi.gouv.fr/api/explore/v2.1/catalog/datasets"
COLONNES = (
    "date",
    "code_region",
    "code_departement",
    "categorie",
    "sexe",
    "tranche_d_age",
    "anciennete",
    "nombre_de_demandeurs_d_emploi",
)
FORMAT = fichier.FormatCSV(encodage="utf-8-sig", separateur=";", decimale=".")
TRIMESTRE = re.compile(r"^(\d{4})-T([1-4])$")
INDICATEURS = {"ABC": "DEMANDEURS_EMPLOI", "A": "DEMANDEURS_EMPLOI_A"}
SEXES = {"Total": "T", "Hommes": "H", "Femmes": "F"}
AGES = {
    "Total": (None, None),
    "Moins de 25 ans": (0, 24),
    "25 à 49 ans": (25, 49),
    "50 ans et plus": (50, None),
}
LONGUE_DUREE = ("anciennete", "UN_AN_OU_PLUS")
# (catégorie, sexe, âge, ancienneté) publiés : total, par sexe, par âge, et pour ABC les
# inscrits depuis un an ou plus. Toute autre combinaison arrête l'import.
VENTILATIONS = frozenset(
    {(c, s, "Total", "Total") for c in INDICATEURS for s in SEXES}
    | {(c, "Total", a, "Total") for c in INDICATEURS for a in AGES}
    | {("ABC", "Total", "Total", "Un an ou plus")}
)
FRANCE = {"Total France": "FR", "Total France métropolitaine": "FM"}


def _territoire(region: str, departement: str) -> tuple[str, str]:
    if region in FRANCE and departement == "Total":
        return "FRANCE", FRANCE[region]
    if departement == "Total":
        return "REG", region
    if re.fullmatch(r"\d{2,3}|2[AB]", departement):
        return "DEP", departement
    raise FichierIllisible(f"Territoire inattendu : {region} / {departement}")


@dataclass(frozen=True)
class DemandeursEmploi:
    source: str = "DARES"
    nom_fichier: str = f"{JEU}.csv"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    # Valeurs arrondies à la dizaine : jusqu'à 0,8 % d'écart entre un total et la somme de
    # ses tranches dans les petits départements (Lozère), 0,03 % pour la France.
    tolerance_sommes: float = 0.01
    controle_couverture: bool = True
    departements_absents: frozenset[str] = frozenset({"976"})

    def fichiers(self) -> list[Fichier]:
        requete = urlencode(
            {
                "select": ",".join(COLONNES),
                "where": 'categorie in ("A","ABC")',
                "order_by": "date,code_region,code_departement",
                "delimiter": ";",
            }
        )
        meta = telechargement.lire_json(f"{API}/{JEU}")
        metas = meta.get("metas", {}) if isinstance(meta, dict) else {}
        modifie = metas.get("default", {}).get("modified")
        return [
            Fichier(
                url=f"{API}/{JEU}/exports/csv?{requete}",
                nom=self.nom_fichier,
                millesime=str(modifie)[:10] if modifie else None,
            )
        ]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        # (territoire, trimestre) -> (inscrits ABC, dont un an ou plus)
        longue_duree: dict[tuple[str, str, date], list[int | None]] = {}
        for brut in fichier.lire_csv(chemin, FORMAT, frozenset(COLONNES)):
            cle = (brut["categorie"], brut["sexe"], brut["tranche_d_age"], brut["anciennete"])
            if cle not in VENTILATIONS:
                raise FichierIllisible(f"Ventilation inattendue : {' / '.join(cle)}")
            trouve = TRIMESTRE.match(brut["date"])
            if not trouve:
                raise FichierIllisible(f"Trimestre illisible : {brut['date']}")
            periode = date(int(trouve[1]), 3 * int(trouve[2]) - 2, 1)
            niveau, code = _territoire(brut["code_region"], brut["code_departement"])
            valeur = fichier.nombre(brut["nombre_de_demandeurs_d_emploi"], ".")
            if valeur is None:
                raise FichierIllisible(f"{niveau} {code} {brut['date']} : valeur vide")
            age_min, age_max = AGES[brut["tranche_d_age"]]
            modalite = LONGUE_DUREE if brut["anciennete"] != "Total" else None
            yield Ligne(INDICATEURS[brut["categorie"]], niveau, code, periode, "TRIMESTRE",
                        SEXES[brut["sexe"]], age_min, age_max, int(valeur), "DEFINITIF",
                        modalite)  # fmt: skip
            if cle[0] == "ABC" and cle[1:3] == ("Total", "Total"):
                termes = longue_duree.setdefault((niveau, code, periode), [None, None])
                termes[1 if modalite else 0] = int(valeur)
        for (niveau, code, periode), (total, dont) in sorted(longue_duree.items()):
            if total and dont is not None:
                part = (Decimal(100) * dont / total).quantize(Decimal("0.1"))
                yield Ligne("PART_LONGUE_DUREE", niveau, code, periode, "TRIMESTRE", "T",
                            None, None, part, "DEFINITIF")  # fmt: skip


DEMANDEURS = DemandeursEmploi()
