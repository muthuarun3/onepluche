"""Valeurs publiées par l'INSEE, pour vérifier que l'application affiche les mêmes chiffres.

Source : INSEE, « Estimation de la population au 1er janvier 2026 », résultats
provisoires arrêtés fin 2025, https://www.insee.fr/fr/statistiques/2012692
(tableau par département : population totale et part des 60 ans ou plus, en %).
Contrôle de sortie de la phase 1 : ces valeurs doivent être retrouvées à l'identique.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Reference:
    niveau: str
    code: str
    libelle: str
    annee: int
    population: int
    part_60_plus: float  # en %, arrondie au dixième comme sur insee.fr


REFERENCES_INSEE = (
    Reference("FRANCE", "FR", "France", 2026, 69_081_996, 28.5),
    Reference("FRANCE", "FM", "France métropolitaine", 2026, 66_792_845, 28.7),
    Reference("DEP", "75", "Paris", 2026, 2_047_602, 24.6),
    Reference("DEP", "23", "Creuse", 2026, 114_943, 40.8),
    Reference("DEP", "59", "Nord", 2026, 2_613_295, 25.2),
    Reference("DEP", "976", "Mayotte", 2026, 338_208, 4.3),
)
