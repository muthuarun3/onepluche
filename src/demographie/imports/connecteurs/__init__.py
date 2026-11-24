"""Un connecteur par source : découverte des fichiers publiés et lecture de leur contenu."""

from demographie.imports.connecteurs.ameli import PATHOLOGIES
from demographie.imports.connecteurs.bdm import CHOMAGE
from demographie.imports.connecteurs.besoins import (
    CHAUFFAGE,
    DEPENSE_PRE_ENGAGEE,
    DEPENSES_MENAGES,
    LOGEMENTS,
    NIVEAU_DE_VIE,
    PAUVRETE,
    POIDS_RP_LOUEES,
    RESIDENCES_PRINCIPALES,
)
from demographie.imports.connecteurs.bmo import BMO
from demographie.imports.connecteurs.climat import CLIMAT
from demographie.imports.connecteurs.comptes_publics import (
    DEPENSES_RECETTES,
    DETTE,
    DETTE_TRIMESTRIELLE,
    ETAGES_APU,
    FONCTIONS_APU,
    PRELEVEMENTS,
    RECETTES_NATURE,
    SOLDE,
)
from demographie.imports.connecteurs.dares import DEMANDEURS
from demographie.imports.connecteurs.delinquance import DELINQUANCE
from demographie.imports.connecteurs.drees import EACR, MINIMUM_VIEILLESSE
from demographie.imports.connecteurs.dvf import VENTES
from demographie.imports.connecteurs.elections import PARTICIPATION_ELECTIONS, VOIX_ELECTIONS
from demographie.imports.connecteurs.energie import DIAGNOSTICS, ELECTRICITE, GAZ, PRIX
from demographie.imports.connecteurs.esr import DISCIPLINES, FORMATIONS
from demographie.imports.connecteurs.estimations import (
    EstimationsDepartements,
    EstimationsRegions,
)
from demographie.imports.connecteurs.loyers import CARTE_DES_LOYERS
from demographie.imports.connecteurs.melodi import DECES, NAISSANCES
from demographie.imports.connecteurs.omphale import PROJECTIONS_DEPARTEMENTALES
from demographie.imports.connecteurs.projections_france import PROJECTIONS_FRANCE
from demographie.imports.connecteurs.recensement import (
    CATEGORIES,
    RECENSEMENT,
    SCOLARISATION,
    SECTEURS,
)
from demographie.imports.connecteurs.ressenti import CVS, VRS_RAPPORTS
from demographie.imports.connecteurs.routes import ACCIDENTS
from demographie.imports.connecteurs.rpls import PARC_SOCIAL
from demographie.imports.connecteurs.soins import (
    ALD_SANS_MEDECIN_TRAITANT,
    APL_MEDECINS,
    MAISONS_DE_SANTE,
    MEDECINS_GENERALISTES,
    PHARMACIES,
    URGENCES,
)
from demographie.imports.connecteurs.transports import (
    DEPENSE_CARBURANTS,
    PRIX_GAZOLE,
    PRIX_SP95_E10,
    TRAJETS_TRAVAIL,
    VOITURES_MENAGES,
)
from demographie.imports.connecteurs.travail import (
    CHOMAGE_ANNUEL,
    CREATIONS,
    DEFAILLANCES,
    EMPLOI_SALARIE,
    EMPLOI_TOTAL,
)
from demographie.imports.connecteurs.vivre import (
    REVENUS_FILOSOFI,
    SALAIRES_AGES,
    SALAIRES_CATEGORIES,
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
    "budget": (DEPENSES_MENAGES, DEPENSE_PRE_ENGAGEE),
    "soins": (
        APL_MEDECINS,
        ALD_SANS_MEDECIN_TRAITANT,
        MEDECINS_GENERALISTES,
        PHARMACIES,
        URGENCES,
        MAISONS_DE_SANTE,
    ),
    # Après « logement » (nombre de ménages) et « budget » : dépenses par ménage.
    "transports": (
        PRIX_GAZOLE,
        PRIX_SP95_E10,
        TRAJETS_TRAVAIL,
        VOITURES_MENAGES,
        DEPENSE_CARBURANTS,
    ),
    # Appli « Les Français sont-ils en sécurité ? »
    "securite": (DELINQUANCE, ACCIDENTS, CVS, VRS_RAPPORTS),
    # Appli 5 : quel avenir pour les Français ? Après « estimations » : la population de
    # départ des projections est comparée aux estimations publiées.
    "avenir": (PROJECTIONS_DEPARTEMENTALES, PROJECTIONS_FRANCE, CLIMAT),
    # Appli 3 : comment vivent les Français ?
    "vivre": (REVENUS_FILOSOFI, SALAIRES_CATEGORIES, SALAIRES_AGES),
    # Appli « Comment travaillent les Français ? »
    "travail": (
        CHOMAGE_ANNUEL,
        EMPLOI_SALARIE,
        EMPLOI_TOTAL,
        CREATIONS,
        DEFAILLANCES,
        DEMANDEURS,
        BMO,
    ),
    # Appli « Où va l'argent public ? » : comptes des administrations publiques (France).
    "argent": (
        DETTE,
        SOLDE,
        DEPENSES_RECETTES,
        RECETTES_NATURE,
        PRELEVEMENTS,
        FONCTIONS_APU,
        ETAGES_APU,
        DETTE_TRIMESTRIELLE,
    ),
    # Appli « Que pensent et votent les Français ? »
    "votes": (PARTICIPATION_ELECTIONS, VOIX_ELECTIONS),
}
