"""Un connecteur par source : découverte des fichiers publiés et lecture de leur contenu."""

from demographie.imports.connecteurs.estimations import (
    EstimationsDepartements,
    EstimationsRegions,
)

CONNECTEURS = {
    "estimations": (EstimationsDepartements(), EstimationsRegions()),
}
