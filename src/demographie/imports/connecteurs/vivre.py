"""Appli 3 « Comment vivent les Français ? » : jeux Melodi de l'INSEE.

- Filosofi (`DS_FILOSOFI_CC`) : déciles, indices d'inégalité et décomposition du revenu
  disponible, une mesure par indicateur, 2023 seul, France métropolitaine et La Réunion.
- Base Tous salariés (`DS_BTS_SAL_EQTP_SEX_PCS`, `DS_BTS_SAL_EQTP_SEX_AGE`) : salaire net
  mensuel moyen en équivalent temps plein du secteur privé, par sexe et catégorie
  socioprofessionnelle, puis par sexe et tranche d'âge.
- Séries nationales (phase A2) : salaire moyen du privé depuis 1996
  (`DS_DERA_PRIVE_SERIES_LONGUES`), niveau de vie et inégalités depuis 1996 (`DS_ERFS_RETROPOLE`,
  France métropolitaine), comptes des ménages (`DD_CNA_AGREGATS` : pouvoir d'achat par unité
  de consommation, revenu disponible, taux d'épargne), patrimoine (`DS_ENQPAT_DET`, enquête
  2024 ; `DD_CNA_PATRIMOINE`, placements financiers).

Même téléchargement que le recensement (API Melodi, niveau par niveau, réponses
assemblées dans un JSON archivé) ; la lecture sait en plus traduire plusieurs mesures d'un
même jeu en plusieurs indicateurs et garder le sexe.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import FichierIllisible, Ligne, Referentiel

_SEXES = {"_T": "T", "F": "F", "M": "H"}
_FRANCE = {"F": "FR", "FM": "FM"}
# Dimensions descriptives qui ne changent pas le sens d'une valeur.
_NEUTRES = {"GEO", "TIME_PERIOD", "FREQ", "UNIT_MEASURE"}


@dataclass(frozen=True)
class JeuMesures(JeuRecensement):
    """Un jeu Melodi dont une dimension (`dimension_mesure`) donne l'indicateur.

    `dimension` (facultative) donne la modalité, `dimension_age` la tranche d'âge et la
    colonne SEX le sexe. Avec `sans_total_age`, les lignes « tous âges » sont ignorées :
    elles sont déjà lues dans un autre jeu (salaires par catégorie).
    """

    indicateur: str = ""
    filtres: dict[str, str] = field(default_factory=dict)
    dimension: str = ""
    dimension_ref: str = ""
    modalites: dict[str, str | None] = field(default_factory=dict)
    ages: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)
    dimension_mesure: str = ""
    mesures: dict[str, str] = field(default_factory=dict)
    sexes: frozenset[str] = frozenset({"_T"})
    sans_total_age: bool = False
    # Indicateurs publiés en négatif par le producteur (impôts retirés du revenu), rangés
    # en positif : le pipeline refuse les valeurs négatives.
    signe_inverse: frozenset[str] = frozenset()
    requete_par_age: bool = False
    periode_type: str = "ANNEE"
    # Code géographique Melodi du niveau France -> code du territoire (les autres sont
    # ignorés) : l'enquête Patrimoine publie la France hors Mayotte (« F_X_D976 »).
    france: dict[str, str] = field(default_factory=lambda: dict(_FRANCE))

    def _territoire(self, geo: str) -> tuple[str, str] | None:
        morceaux = geo.split("-", 2)
        if len(morceaux) == 3 and morceaux[1] == "FRANCE":
            code = self.france.get(morceaux[2])
            return ("FRANCE", code) if code else None
        return super()._territoire(geo)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            observations = json.loads(chemin.read_text(encoding="utf-8"))["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not observations:
            raise FichierIllisible("Aucune observation")
        connues = _NEUTRES | {"SEX", self.dimension_mesure, *self.filtres}
        if self.dimension:
            connues.add(self.dimension)
        if self.ages:
            connues.add(self.dimension_age)
        lues = 0
        for obs in observations:
            dim = obs.get("dimensions") if isinstance(obs, dict) else None
            if not isinstance(dim, dict) or self.dimension_mesure not in dim:
                raise FichierIllisible(f"Observation illisible : {obs}")
            indicateur = self.mesures.get(dim[self.dimension_mesure])
            if indicateur is None:
                continue  # mesure non retenue
            if dim.get("SEX", "_T") not in self.sexes:
                continue
            if self.dimension and dim.get(self.dimension) not in self.modalites:
                continue
            if self.ages:
                age = dim.get(self.dimension_age)
                if age not in self.ages or (self.sans_total_age and age == "_T"):
                    continue
            inattendues = {
                k: v
                for k, v in dim.items()
                if (k in self.filtres and v != self.filtres[k]) or (k not in connues and v != "_T")
            }
            if inattendues:
                raise FichierIllisible(f"Dimensions inattendues : {inattendues}")
            territoire = self._territoire(dim.get("GEO", ""))
            if territoire is None:
                continue
            try:
                valeur = Decimal(str(obs["measures"]["OBS_VALUE_NIVEAU"]["value"]))
            except (KeyError, TypeError, ArithmeticError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            if indicateur in self.signe_inverse:
                valeur = -valeur
            age_min, age_max = self.ages[dim[self.dimension_age]] if self.ages else (None, None)
            modalite = self.modalites[dim[self.dimension]] if self.dimension else None
            lues += 1
            yield Ligne(
                indicateur=indicateur,
                niveau=territoire[0],
                code=territoire[1],
                periode=date(int(dim["TIME_PERIOD"]), 1, 1),
                periode_type=self.periode_type,
                sexe=_SEXES[dim.get("SEX", "_T")],
                age_min=age_min,
                age_max=age_max,
                valeur=valeur,
                statut=(
                    "PROVISOIRE"
                    if (obs.get("attributes") or {}).get("OBS_STATUS") in self.statuts_provisoires
                    else "DEFINITIF"
                ),
                modalite=(self.dimension_ref, modalite) if modalite else None,
            )
        if not lues:
            raise FichierIllisible("Aucune mesure attendue dans le fichier")


# Filosofi ne couvre que la France métropolitaine et La Réunion (aucun total « FR »).
_FILOSOFI_ABSENTS = frozenset({"971", "972", "973", "976"})

REVENUS_FILOSOFI = JeuMesures(
    jeu="DS_FILOSOFI_CC",
    source="INSEE_FILOSOFI",
    dimension_mesure="FILOSOFI_MEASURE",
    mesures={
        "D1_SL": "NIVEAU_VIE_D1",
        "D9_SL": "NIVEAU_VIE_D9",
        "IR_D9_D1_SL": "RAPPORT_D9_D1",
        "GI_SL": "INDICE_GINI",
        "S80S20_SL": "RAPPORT_S80_S20",
        "S_EI_DI": "PART_REVENUS_ACTIVITE",
        "S_EI_DI_SAL": "PART_SALAIRES",
        "S_EI_DI_UNE": "PART_CHOMAGE",
        "S_INC_ASS_DI": "PART_REVENUS_PATRIMOINE",
        "S_SOC_BEN_DI": "PART_PRESTATIONS",
        "S_DIR_TAX_DI": "PART_IMPOTS",
        "S_SOC_BEN_DI_MIN_SOC": "PART_MINIMA_SOCIAUX",
        "S_SOC_BEN_DI_HOU_BEN": "PART_AIDES_LOGEMENT",
        "S_RET_PEN_DI": "PART_PENSIONS",
    },
    signe_inverse=frozenset({"PART_IMPOTS"}),
    controle_couverture=True,
    departements_absents=_FILOSOFI_ABSENTS,
)

_SALAIRE = {"DERA_MEASURE": "SALAIRE_NET_EQTP_MENSUEL_MOYENNE"}
_TOUS_SEXES = frozenset({"_T", "F", "M"})

SALAIRES_CATEGORIES = JeuMesures(
    jeu="DS_BTS_SAL_EQTP_SEX_PCS",
    source="INSEE_BTS",
    filtres=_SALAIRE,
    dimension_mesure="DERA_MEASURE",
    mesures={"SALAIRE_NET_EQTP_MENSUEL_MOYENNE": "SALAIRE_NET_MOYEN"},
    sexes=_TOUS_SEXES,
    dimension="PCS_ESE",
    dimension_ref="pcs",
    modalites={
        "_T": None,
        "1T3": "CADRES_DIRIGEANTS",
        "4": "PROF_INTERMEDIAIRES",
        "5": "EMPLOYES",
        "6": "OUVRIERS",
    },
    controle_couverture=True,
)

SALAIRES_AGES = JeuMesures(
    jeu="DS_BTS_SAL_EQTP_SEX_AGE",
    source="INSEE_BTS",
    filtres=_SALAIRE,
    dimension_mesure="DERA_MEASURE",
    mesures={"SALAIRE_NET_EQTP_MENSUEL_MOYENNE": "SALAIRE_NET_MOYEN"},
    sexes=_TOUS_SEXES,
    ages={
        "_T": (None, None),
        "Y_LT25": (0, 24),
        "Y25T39": (25, 39),
        "Y40T49": (40, 49),
        "Y50T54": (50, 54),
        "Y_GE55": (55, None),
    },
    sans_total_age=True,
)

# Séries nationales (phase A2). Un appel ou deux par jeu, niveau France seulement.
_NATIONAL = {
    "niveaux_geo": ("FRANCE",),
    "niveaux_publies": frozenset({"FRANCE"}),
}

# Salaire net moyen du privé en équivalent temps plein, en euros constants de la dernière
# année publiée, depuis 1996 (France métropolitaine jusqu'en 1999, France ensuite).
SALAIRE_SERIE = JeuMesures(
    jeu="DS_DERA_PRIVE_SERIES_LONGUES",
    source="INSEE_BTS",
    filtres={
        "DERA_MEASURE": "SALAIRE_NET_EQTP_MENSUEL_MOYEN_EUROS_CONSTANTS",
        "NUMBER_EMPL": "_T",
        "QUANTILE": "_T",
        "WKTIME": "_T",
        "PCS_ESE": "_T",
        "ACTIVITY": "_T",
        "AGE": "_T",
    },
    dimension_mesure="DERA_MEASURE",
    mesures={"SALAIRE_NET_EQTP_MENSUEL_MOYEN_EUROS_CONSTANTS": "SALAIRE_PRIVE_SERIE"},
    sexes=_TOUS_SEXES,
    **_NATIONAL,
)

# Enquête Revenus fiscaux et sociaux rétropolée : France métropolitaine depuis 1996, niveau
# de vie en euros constants de la dernière année.
NIVEAU_VIE_SERIES = JeuMesures(
    jeu="DS_ERFS_RETROPOLE",
    source="INSEE_ERFS",
    filtres={"EMPSTA_ENQ": "_T", "TPH": "_T", "MUN_DENSITY_LEVEL": "_T", "AGE": "_T"},
    dimension_mesure="ERFS_MEASURE",
    mesures={
        "MED_SL": "NIVEAU_VIE_MEDIAN_SERIE",
        "PR_MD60": "TAUX_PAUVRETE_SERIE",
        "GI_SL": "GINI_SERIE",
        "IR_D9_D1_SL": "RAPPORT_D9_D1_SERIE",
    },
    **_NATIONAL,
)

# Comptes nationaux annuels, ménages au sens strict (S14). Un fichier par agrégat : leurs
# dimensions fixes diffèrent (évolution, niveau, taux).
_MENAGES = {
    "REF_SECTOR": "S14",
    "COUNTERPART_AREA": "W0",
    "PRODUCT": "_T",
    "INSTR_ASSET": "_Z",
    "EXPENDITURE": "_Z",
    "ACTIVITY": "_T",
    "PRICES": "V",
}


def _comptes(suffixe: str, sto: str, indicateur: str, **filtres: str) -> JeuMesures:
    return JeuMesures(
        jeu="DD_CNA_AGREGATS",
        suffixe=suffixe,
        source="INSEE_CNA",
        filtres={**_MENAGES, "STO": sto, **filtres},
        dimension_mesure="STO",
        mesures={sto: indicateur},
        statuts_provisoires=frozenset({"P"}),
        **_NATIONAL,
    )


POUVOIR_ACHAT = _comptes(
    "_pouvoir_achat", "_PAM_UC", "POUVOIR_ACHAT_UC",
    TRANSFORMATION="GY", ACCOUNTING_ENTRY="_Z", UNIT_MEASURE="PT",
)  # fmt: skip
REVENU_DISPONIBLE = _comptes(
    "_revenu_disponible", "B6G", "REVENU_DISPONIBLE",
    TRANSFORMATION="N", ACCOUNTING_ENTRY="B", UNIT_MEASURE="XDC",
)  # fmt: skip
TAUX_EPARGNE = _comptes(
    "_taux_epargne", "_TEM", "TAUX_EPARGNE",
    TRANSFORMATION="N", ACCOUNTING_ENTRY="_Z", UNIT_MEASURE="PT",
)  # fmt: skip
TAUX_EPARGNE_FINANCIERE = _comptes(
    "_taux_epargne_financiere", "_TEFM", "TAUX_EPARGNE_FINANCIERE",
    TRANSFORMATION="N", ACCOUNTING_ENTRY="_Z", UNIT_MEASURE="PT",
)  # fmt: skip

# Encours des placements financiers des ménages (comptes de patrimoine, fin d'année, en
# millions d'euros). Les placements non retenus (crédits, produits dérivés…) sont ignorés.
PATRIMOINE_FINANCIER = JeuMesures(
    jeu="DD_CNA_PATRIMOINE",
    source="INSEE_CNA",
    filtres={
        "REF_SECTOR": "S14",
        "STO": "LE",
        "ACCOUNTING_ENTRY": "D",
        "MATURITY": "_Z",
        "PRICES": "U",
        "TRANSFORMATION": "N",
        "UNIT_MEASURE": "XDC",
        "COUNTERPART_AREA": "W0",
        "COUNTERPART_SECTOR": "S1",
        "CONSOLIDATION": "N",
        "VALUATION": "S",
        "EXPENDITURE": "_Z",
        "PRODUCT": "_T",
        "ACTIVITY": "_T",
    },
    dimension_mesure="STO",
    mesures={"LE": "PATRIMOINE_FINANCIER"},
    dimension="INSTR_ASSET",
    dimension_ref="placement",
    modalites={
        "F": None,
        "F2": "DEPOTS",
        "F3": "TITRES_CREANCE",
        "F51": "ACTIONS",
        "F52": "FONDS",
        "F62": "ASSURANCE_VIE",
    },
    statuts_provisoires=frozenset({"P"}),
    **_NATIONAL,
)

# Enquête Histoire de vie et Patrimoine 2023-2024 : France hors Mayotte, patrimoine des
# ménages selon l'âge et la catégorie de la personne de référence, et selon le décile de
# niveau de vie. Trois fichiers : chaque ventilation est demandée à part à l'API.
_PATRIMOINE = {
    "jeu": "DS_ENQPAT_DET",
    "source": "INSEE_ENQPAT",
    "dimension_mesure": "ENQPAT_MEASURE",
    "france": {"F_X_D976": "FR"},
    **_NATIONAL,
}
_SANS_VENTILATION = {"COMPARE_TIME": "_Z", "DEG_URB_UNIT": "_T", "TPH": "_T"}

PATRIMOINE_AGES = JeuMesures(
    suffixe="_ages",
    filtres={**_SANS_VENTILATION, "PCS": "_T", "QUANTILE": "_T", "QUANTILE_MEASURE": "_T"},
    mesures={"MT_MOY_PATBRUT": "PATRIMOINE_BRUT_MOYEN", "MT_MED_PATNET": "PATRIMOINE_NET_MEDIAN"},
    ages={
        "_T": (None, None),
        "Y_LT30": (0, 29),
        "Y30T39": (30, 39),
        "Y40T49": (40, 49),
        "Y50T59": (50, 59),
        "Y60T69": (60, 69),
        "Y_GE70": (70, None),
    },
    **_PATRIMOINE,
)

# Sans le total (lu avec les âges) ni les regroupements (cadres et professions libérales…).
PATRIMOINE_CATEGORIES = JeuMesures(
    suffixe="_categories",
    filtres={**_SANS_VENTILATION, "AGE": "_T", "QUANTILE": "_T", "QUANTILE_MEASURE": "_T"},
    mesures={"MT_MOY_PATBRUT": "PATRIMOINE_BRUT_MOYEN"},
    dimension="PCS",
    dimension_ref="pcs",
    modalites={
        "10": "AGRICULTEURS",
        "20": "ARTISANS_COMMERCANTS",
        "31": "PROFESSIONS_LIBERALES",
        "3_X_31": "CADRES_HORS_LIBERALES",
        "4": "PROF_INTERMEDIAIRES",
        "50": "EMPLOYES",
        "60": "OUVRIERS",
        "71T72": "RETRAITES_INDEPENDANTS",
        "73": "RETRAITES_CADRES",
        "75": "RETRAITES_PROF_INTERMEDIAIRES",
        "77T78": "RETRAITES_EMPLOYES_OUVRIERS",
        "91": "INACTIFS_JAMAIS_TRAVAILLE",
    },
    **_PATRIMOINE,
)

PATRIMOINE_DECILES = JeuMesures(
    suffixe="_deciles",
    filtres={**_SANS_VENTILATION, "AGE": "_T", "PCS": "_T", "QUANTILE_MEASURE": "NIVVIE"},
    mesures={"MT_MOY_PATBRUT": "PATRIMOINE_BRUT_MOYEN"},
    dimension="QUANTILE",
    dimension_ref="decile_niveau_vie",
    modalites={f"D{i}TD{i + 1}": f"D{i + 1:02d}" for i in range(10)},
    **_PATRIMOINE,
)

SERIES_NATIONALES = (
    SALAIRE_SERIE,
    NIVEAU_VIE_SERIES,
    POUVOIR_ACHAT,
    REVENU_DISPONIBLE,
    TAUX_EPARGNE,
    TAUX_EPARGNE_FINANCIERE,
    PATRIMOINE_FINANCIER,
    PATRIMOINE_AGES,
    PATRIMOINE_CATEGORIES,
    PATRIMOINE_DECILES,
)
