"""Un connecteur par source : découverte des fichiers publiés et lecture de leur contenu."""

from demographie.imports.connecteurs.ameli import PATHOLOGIES
from demographie.imports.connecteurs.bdm import CHOMAGE
from demographie.imports.connecteurs.besoins import (
    CHAUFFAGE,
    LOGEMENTS,
    NIVEAU_DE_VIE,
    PAUVRETE,
    RESIDENCES_PRINCIPALES,
)
from demographie.imports.connecteurs.drees import EACR, MINIMUM_VIEILLESSE
from demographie.imports.connecteurs.esr import DISCIPLINES, FORMATIONS
from demographie.imports.connecteurs.estimations import (
    EstimationsDepartements,
    EstimationsRegions,
)
from demographie.imports.connecteurs.melodi import DECES, NAISSANCES
from demographie.imports.connecteurs.recensement import (
    CATEGORIES,
    RECENSEMENT,
    SCOLARISATION,
    SECTEURS,
)

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
    "logement": (LOGEMENTS, RESIDENCES_PRINCIPALES, CHAUFFAGE, NIVEAU_DE_VIE, PAUVRETE),
}
