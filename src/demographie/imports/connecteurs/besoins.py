"""Sources de l'appli 2 « De quoi les Français ont-ils besoin ? » (dossier de conception
de l'appli 2, étape 6). Les jeux Melodi du recensement et de Filosofi réutilisent le
connecteur du recensement ; les autres sources ont leur propre module.
"""

import dataclasses
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import Ligne, Referentiel

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
