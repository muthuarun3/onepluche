"""Sources de l'appli 2 « De quoi les Français ont-ils besoin ? » (dossier de conception
de l'appli 2, étape 6). Les jeux Melodi du recensement et de Filosofi réutilisent le
connecteur du recensement ; les autres sources ont leur propre module.
"""

import dataclasses
import json
from collections import defaultdict
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import FichierIllisible, Ligne, Poids, Referentiel

# Les autres dimensions du jeu logement, fixées à leur total.
_LOGEMENT_TOTAUX = {
    "RP_MEASURE": "DWELLINGS",
    "CARS": "_T",
    "BUILD_END": "_T",
    "TDW": "_T",
    "CARPARK": "_T",
    "NOR": "_T",
    "L_STAY": "_T",
}
# Mayotte a son propre recensement (jeux « DOM »), absent de ces jeux.
_SANS_MAYOTTE = frozenset({"976"})

LOGEMENTS = JeuRecensement(
    jeu="DS_RP_LOGEMENT_PRINC",
    suffixe="_categories",
    indicateur="LOGEMENTS",
    filtres={**_LOGEMENT_TOTAUX, "TSH": "_T", "NRG_SRC": "_T"},
    dimension="OCS",
    dimension_ref="categorie_logement",
    modalites={
        "_T": None,
        "DW_MAIN": "RESIDENCE_PRINCIPALE",
        "DW_SEC_DW_OCC": "RESIDENCE_SECONDAIRE",
        "DW_VAC": "VACANT",
    },
    ages={},
    requete_par_age=False,
    controle_couverture=True,
    departements_absents=_SANS_MAYOTTE,
)

RESIDENCES_PRINCIPALES = JeuRecensement(
    jeu="DS_RP_LOGEMENT_PRINC",
    suffixe="_statut_occupation",
    indicateur="RESIDENCES_PRINC",
    filtres={**_LOGEMENT_TOTAUX, "OCS": "DW_MAIN", "NRG_SRC": "_T"},
    dimension="TSH",
    dimension_ref="statut_occupation",
    # 200 (tous les locataires) n'est pas repris : il double 211 + 221 + 212_222.
    modalites={
        "_T": None,
        "100": "PROPRIETAIRE",
        "211": "LOCATAIRE_PRIVE",
        "221": "LOCATAIRE_HLM",
        "212_222": "LOCATAIRE_MEUBLE",
        "300": "LOGE_GRATUIT",
    },
    ages={},
    requete_par_age=False,
    controle_couverture=True,
    departements_absents=_SANS_MAYOTTE,
)

_HORS_CHAMP = "_Z"


@dataclasses.dataclass(frozen=True)
class JeuChauffage(JeuRecensement):
    """Combustible principal du chauffage.

    La question n'est pas posée en outre-mer : ces logements sont classés « _Z » (hors
    champ). Le total publié ne garde que les logements au mode de chauffage connu, pour
    que la part du fioul ne soit pas diluée ; un territoire sans aucun logement dans le
    champ (DROM) n'est pas publié.
    """

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        series: dict[tuple, list[Ligne]] = defaultdict(list)
        for ligne in super().lire(chemin, referentiel):
            series[(ligne.niveau, ligne.code, ligne.periode)].append(ligne)
        for lignes in series.values():
            hors_champ = sum(
                (x.valeur for x in lignes if x.modalite == (self.dimension_ref, _HORS_CHAMP)), 0
            )
            total = sum((x.valeur for x in lignes if x.modalite is None), 0) - hors_champ
            if total <= 0:
                continue
            for ligne in lignes:
                if ligne.modalite is None:
                    yield dataclasses.replace(ligne, valeur=total)
                elif ligne.modalite[1] != _HORS_CHAMP:
                    yield ligne


CHAUFFAGE = JeuChauffage(
    jeu="DS_RP_LOGEMENT_PRINC",
    suffixe="_chauffage",
    indicateur="RESIDENCES_PRINC_CHAUFFAGE",
    filtres={**_LOGEMENT_TOTAUX, "OCS": "DW_MAIN", "TSH": "_T"},
    dimension="NRG_SRC",
    dimension_ref="combustible",
    modalites={
        "_T": None,
        "ELC": "ELECTRICITE",
        "TOWN_GAS": "GAZ_RESEAU",
        "BOT_GAS": "GAZ_BOUTEILLE",
        "OIL": "FIOUL",
        "OTH": "AUTRE",
        _HORS_CHAMP: _HORS_CHAMP,
    },
    ages={},
    requete_par_age=False,
)

# Filosofi : niveau de vie et pauvreté, par statut d'occupation et tranche d'âge de la
# personne de référence du ménage. Les 18-39 ans servent l'encadré de la fiche.
_FILOSOFI_AGES = {"_T": (None, None), "Y18T29": (18, 29), "Y30T39": (30, 39)}
_FILOSOFI_STATUTS = {"_T": None, "1": "PROPRIETAIRE", "2": "LOCATAIRE"}
# Filosofi ne couvre que la France métropolitaine et La Réunion (aucun total « FR »).
_FILOSOFI_ABSENTS = frozenset({"971", "972", "973", "976"})

NIVEAU_DE_VIE = JeuRecensement(
    jeu="DS_FILOSOFI_SAGE_LOG_TP_NIVVIE",
    suffixe="_niveau_vie",
    source="INSEE_FILOSOFI",
    indicateur="NIVEAU_VIE_MEDIAN",
    filtres={"SEX": "_T", "FILOSOFI_MEASURE": "MED_SL", "UNIT_MEASURE": "EUR_YR"},
    dimension="TSH",
    dimension_ref="statut_occupation",
    modalites=_FILOSOFI_STATUTS,
    ages=_FILOSOFI_AGES,
    dimension_age="AGE_GP",
    periode_type="ANNEE",
    controle_couverture=True,
    departements_absents=_FILOSOFI_ABSENTS,
)

PAUVRETE = JeuRecensement(
    jeu="DS_FILOSOFI_SAGE_LOG_TP_NIVVIE",
    suffixe="_pauvrete",
    source="INSEE_FILOSOFI",
    indicateur="TAUX_PAUVRETE",
    filtres={"SEX": "_T", "FILOSOFI_MEASURE": "PR_MD60", "UNIT_MEASURE": "PT"},
    dimension="TSH",
    dimension_ref="statut_occupation",
    modalites=_FILOSOFI_STATUTS,
    ages=_FILOSOFI_AGES,
    dimension_age="AGE_GP",
    periode_type="ANNEE",
    controle_couverture=True,
    departements_absents=_FILOSOFI_ABSENTS,
)


@dataclasses.dataclass(frozen=True)
class PoidsRecensement(JeuRecensement):
    """Poids communaux tirés du recensement, pour ramener une source communale au
    département. Les arrondissements de Paris, Lyon et Marseille sont lus avec les
    communes : la Carte des loyers les détaille.
    """

    poids_communaux: bool = True
    communes_min: int = 30_000

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Poids]:
        try:
            observations = json.loads(chemin.read_text(encoding="utf-8"))["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        for obs in observations:
            try:
                dim = obs["dimensions"]
                mesure = obs["measures"]["OBS_VALUE_NIVEAU"]
                if "value" not in mesure:
                    continue  # commune absente de ce millésime (fusion, création)
                valeur = Decimal(str(mesure["value"]))
                _millesime, niveau, commune = dim["GEO"].split("-", 2)
                annee = int(dim["TIME_PERIOD"])
            except (KeyError, TypeError, ValueError, ArithmeticError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            inattendues = {k: v for k, v in self.filtres.items() if dim.get(k, v) != v}
            if inattendues or niveau not in self.niveaux_geo:
                raise FichierIllisible(f"Observation inattendue : {dim}")
            yield Poids(self.indicateur, annee, commune, valeur)


# Résidences principales louées (vides ou meublées, parc privé et social) de chaque
# commune : poids de la Carte des loyers.
POIDS_RP_LOUEES = PoidsRecensement(
    jeu="DS_RP_LOGEMENT_PRINC",
    suffixe="_communes_louees",
    indicateur="RP_LOUEES",
    filtres={**_LOGEMENT_TOTAUX, "OCS": "DW_MAIN", "TSH": "200", "NRG_SRC": "_T"},
    dimension="TSH",
    dimension_ref="statut_occupation",
    modalites={"200": None},
    ages={},
    requete_par_age=False,
    niveaux_geo=("COM", "ARM"),
    niveaux_publies=frozenset(),
)


# Comptes nationaux (INSEE, Melodi) : dépense de consommation des ménages par fonction
# (nomenclature COICOP 2018, 13 postes), en millions d'euros courants, France entière.
# Les trois dernières années sont provisoires ou semi-définitives (OBS_STATUS « P »).
_COMPTES = {
    "PRICES": "V",
    "TRANSFORMATION": "N",
    "COUNTERPART_AREA": "W2",
    "REF_SECTOR": "S14",
    "INSTR_ASSET": "_Z",
    "PRODUCT": "_T",  # hors détail des services d'assurance
}
POSTES_CONSO = {
    "_Z": None,
    "CP01": "ALIMENTATION",
    "CP02": "ALCOOL_TABAC",
    "CP03": "HABILLEMENT",
    "CP04": "LOGEMENT",
    "CP05": "EQUIPEMENT_MAISON",
    "CP06": "SANTE",
    "CP07": "TRANSPORTS",
    "CP08": "COMMUNICATION",
    "CP09": "LOISIRS",
    "CP10": "ENSEIGNEMENT",
    "CP11": "RESTAURANTS_HOTELS",
    "CP12": "ASSURANCES_FINANCE",
    "CP13": "AUTRES",
}

DEPENSES_MENAGES = JeuRecensement(
    jeu="DD_CNA_CONSO_MENAGES_COICOP",
    suffixe="_depense",
    source="INSEE_CNA",
    indicateur="DEPENSE_CONSO_MENAGES",
    filtres={**_COMPTES, "STO": "P31", "UNIT_MEASURE": "XDC", "ACCOUNTING_ENTRY": "D"},
    dimension="EXPENDITURE",
    dimension_ref="poste_conso",
    modalites=POSTES_CONSO,
    ages={},
    requete_par_age=False,
    niveaux_geo=("FRANCE",),
    niveaux_publies=frozenset({"FRANCE"}),
    periode_type="ANNEE",
    statuts_provisoires=frozenset({"P"}),
)

# Dépenses « pré-engagées » (logement, énergie, assurances, abonnements, cantines…) en
# part du revenu disponible brut des ménages.
DEPENSE_PRE_ENGAGEE = JeuRecensement(
    jeu="DD_CNA_CONSO_MENAGES_COICOP",
    suffixe="_pre_engagee",
    source="INSEE_CNA",
    indicateur="PART_DEPENSE_PRE_ENGAGEE",
    filtres={**_COMPTES, "STO": "_DEP_REVENU", "UNIT_MEASURE": "PT", "ACCOUNTING_ENTRY": "_Z"},
    dimension="EXPENDITURE",
    dimension_ref="poste_conso",
    modalites={"CPDPE": None},
    ages={},
    requete_par_age=False,
    niveaux_geo=("FRANCE",),
    niveaux_publies=frozenset({"FRANCE"}),
    periode_type="ANNEE",
    statuts_provisoires=frozenset({"P"}),
)
