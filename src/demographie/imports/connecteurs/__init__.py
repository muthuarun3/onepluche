"""Un connecteur par source : découverte des fichiers publiés et lecture de leur contenu."""

from demographie.imports.connecteurs.ameli import PATHOLOGIES
from demographie.imports.connecteurs.bdm import CHOMAGE
from demographie.imports.connecteurs.besoins import (
    CHAUFFAGE,
    LOGEMENTS,
    NIVEAU_DE_VIE,
    PAUVRETE,
    POIDS_RP_LOUEES,
    RESIDENCES_PRINCIPALES,
)
from demographie.imports.connecteurs.drees import EACR, MINIMUM_VIEILLESSE
from demographie.imports.connecteurs.dvf import VENTES
from demographie.imports.connecteurs.energie import DIAGNOSTICS, ELECTRICITE, GAZ, PRIX
from demographie.imports.connecteurs.esr import DISCIPLINES, FORMATIONS
from demographie.imports.connecteurs.estimations import (
    EstimationsDepartements,
    EstimationsRegions,
)
from demographie.imports.connecteurs.loyers import CARTE_DES_LOYERS
from demographie.imports.connecteurs.melodi import DECES, NAISSANCES
from demographie.imports.connecteurs.recensement import (
    CATEGORIES,
    RECENSEMENT,
    SCOLARISATION,
    SECTEURS,
)
from demographie.imports.connecteurs.rpls import PARC_SOCIAL

# Ordre d'exécution de « demo importer tout » : les estimations d'abord.
CONNECTEURS = {
    "estimations": (EstimationsDepartements(), EstimationsRegions()),
    "etat-civil": (NAISSANCES, DECES),
    "chomage": (CHOMAGE,),
    "recensement": (RECENSEMENT, CATEGORIES, SECTEURS, SCOLARISATION),
    "retraites": (EACR, MINIMUM_VIEILLESSE),
    "etudiants": (FORMATIONS, DISCIPLINES),
    "sante": (PATHOLOGIES,),
    # Appli 2 : de quoi les Français ont-ils besoin ?
    # Les poids communaux avant la Carte des loyers, qui les utilise.
    "logement": (
        LOGEMENTS,
        RESIDENCES_PRINCIPALES,
        CHAUFFAGE,
        NIVEAU_DE_VIE,
        PAUVRETE,
        POIDS_RP_LOUEES,
        CARTE_DES_LOYERS,
        VENTES,
        PARC_SOCIAL,
    ),
    "energie": (ELECTRICITE, GAZ, DIAGNOSTICS, PRIX),
}
