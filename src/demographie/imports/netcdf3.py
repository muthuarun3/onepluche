"""Lecture des fichiers NetCDF « classiques » (formats CDF-1 et CDF-2), sans dépendance.

Format décrit par Unidata (« NetCDF Classic Format Specification ») : un en-tête (dimensions,
attributs, variables avec leur position dans le fichier) puis les données, en gros-boutiste.
Les variables d'enregistrement (première dimension illimitée, ici ``time``) sont lues comme
les autres : un enregistrement après l'autre, entrelacés avec les autres variables
d'enregistrement. Les climatologies de la Banque mondiale ont un seul enregistrement.
"""

import struct
from dataclasses import dataclass, field
from pathlib import Path

_ABSENT, _DIMENSION, _VARIABLE, _ATTRIBUT = 0, 10, 11, 12
# type NetCDF -> (format struct, taille en octets)
_TYPES = {1: ("b", 1), 2: ("c", 1), 3: ("h", 2), 4: ("i", 4), 5: ("f", 4), 6: ("d", 8)}


class NetCDFIllisible(ValueError):
    """Le fichier n'est pas un NetCDF classique lisible."""


@dataclass
class Variable:
    nom: str
    dimensions: tuple[str, ...]
    forme: tuple[int, ...]
    attributs: dict
    type_nc: int
    debut: int
    # Variables d'enregistrement : taille d'un enregistrement de toutes les variables.
    pas_enregistrement: int = 0

    @property
    def taille_valeur(self) -> int:
        return _TYPES[self.type_nc][1]


@dataclass
class NetCDF:
    dimensions: dict[str, int]
    attributs: dict
    variables: dict[str, Variable] = field(default_factory=dict)
    octets: bytes = b""

    def valeurs(self, nom: str) -> list:
        """Toutes les valeurs d'une variable, à plat (ordre C)."""
        v = self.variables[nom]
        if v.pas_enregistrement:
            n = _produit(v.forme[1:])
            return [
                x
                for r in range(v.forme[0])
                for x in self._lire(v, v.debut + r * v.pas_enregistrement, n)
            ]
        return self._lire(v, v.debut, _produit(v.forme))

    def ligne(self, nom: str, *indices: int) -> list:
        """La dernière dimension d'une variable, les autres fixées par ``indices``."""
        v = self.variables[nom]
        if len(indices) != len(v.forme) - 1:
            raise NetCDFIllisible(f"{nom} : {len(v.forme) - 1} indice(s) attendu(s)")
        debut, indices, forme = v.debut, list(indices), list(v.forme)
        if v.pas_enregistrement:
            debut += indices.pop(0) * v.pas_enregistrement
            forme.pop(0)
        decalage = 0
        for i, taille in zip(indices, forme[:-1], strict=True):
            if not 0 <= i < taille:
                raise NetCDFIllisible(f"{nom} : indice {i} hors de 0..{taille - 1}")
            decalage = decalage * taille + i
        decalage *= forme[-1]
        return self._lire(v, debut + decalage * v.taille_valeur, forme[-1])

    def _lire(self, v: Variable, debut: int, n: int) -> list:
        code, taille = _TYPES[v.type_nc]
        brut = self.octets[debut : debut + n * taille]
        if len(brut) != n * taille:
            raise NetCDFIllisible(f"{v.nom} : données tronquées")
        valeurs = list(struct.unpack(f">{n}{code}", brut))
        manquante = v.attributs.get("_FillValue", v.attributs.get("missing_value"))
        if isinstance(manquante, list):
            manquante = manquante[0] if manquante else None
        echelle = _scalaire(v.attributs.get("scale_factor"))
        ajout = _scalaire(v.attributs.get("add_offset"))
        resultat = []
        for x in valeurs:
            if manquante is not None and x == manquante or x != x:  # NaN
                resultat.append(None)
                continue
            if echelle is not None:
                x = x * echelle
            if ajout is not None:
                x = x + ajout
            resultat.append(x)
        return resultat


def _produit(forme) -> int:
    n = 1
    for d in forme:
        n *= d
    return n


def _scalaire(valeur):
    if isinstance(valeur, list):
        return valeur[0] if valeur else None
    return valeur


class _Lecteur:
    def __init__(self, octets: bytes):
        self.octets = octets
        self.pos = 0

    def entier(self) -> int:
        (x,) = struct.unpack_from(">i", self.octets, self.pos)
        self.pos += 4
        return x

    def entier64(self) -> int:
        (x,) = struct.unpack_from(">q", self.octets, self.pos)
        self.pos += 8
        return x

    def nom(self) -> str:
        n = self.entier()
        texte = self.octets[self.pos : self.pos + n].decode("utf-8")
        self.pos += n + (-n % 4)
        return texte

    def valeurs(self, type_nc: int, n: int):
        if type_nc not in _TYPES:
            raise NetCDFIllisible(f"Type NetCDF inconnu : {type_nc}")
        code, taille = _TYPES[type_nc]
        brut = self.octets[self.pos : self.pos + n * taille]
        self.pos += n * taille + (-(n * taille) % 4)
        if type_nc == 2:
            return brut.decode("utf-8", errors="replace").rstrip("\x00")
        return list(struct.unpack(f">{n}{code}", brut))

    def attributs(self) -> dict:
        etiquette, n = self.entier(), self.entier()
        if etiquette == _ABSENT:
            return {}
        if etiquette != _ATTRIBUT:
            raise NetCDFIllisible("Liste d'attributs attendue")
        resultat = {}
        for _ in range(n):
            nom = self.nom()
            type_nc = self.entier()
            resultat[nom] = self.valeurs(type_nc, self.entier())
        return resultat


def lire(chemin: Path) -> NetCDF:
    """Lit l'en-tête et garde les octets ; les valeurs se lisent ensuite à la demande."""
    return lire_octets(Path(chemin).read_bytes())


def lire_octets(octets: bytes) -> NetCDF:
    """Comme `lire`, depuis des octets. Le début du fichier suffit pour lire l'en-tête
    (dimensions, attributs, position des variables) ; lire une valeur au-delà échoue."""
    if octets[:3] != b"CDF" or octets[3] not in (1, 2):
        if octets[:4] == b"\x89HDF":
            raise NetCDFIllisible("Fichier NetCDF-4 (HDF5) : format non pris en charge")
        raise NetCDFIllisible("Ce n'est pas un fichier NetCDF classique")
    decalage64 = octets[3] == 2
    lecteur = _Lecteur(octets)
    if len(octets) < 8:
        raise NetCDFIllisible("En-tête tronqué")
    lecteur.pos = 4
    enregistrements = lecteur.entier()
    dimensions: dict[str, int] = {}
    noms_dimensions: list[str] = []
    etiquette, n = lecteur.entier(), lecteur.entier()
    if etiquette not in (_ABSENT, _DIMENSION):
        raise NetCDFIllisible("Liste de dimensions attendue")
    for _ in range(n if etiquette == _DIMENSION else 0):
        nom = lecteur.nom()
        dimensions[nom] = lecteur.entier()
        noms_dimensions.append(nom)
    fichier = NetCDF(dimensions=dimensions, attributs=lecteur.attributs(), octets=octets)
    etiquette, n = lecteur.entier(), lecteur.entier()
    if etiquette not in (_ABSENT, _VARIABLE):
        raise NetCDFIllisible("Liste de variables attendue")
    a_enregistrer = []
    for _ in range(n if etiquette == _VARIABLE else 0):
        nom = lecteur.nom()
        ids = [lecteur.entier() for _ in range(lecteur.entier())]
        attributs = lecteur.attributs()
        type_nc = lecteur.entier()
        taille = lecteur.entier()  # vsize : octets d'un enregistrement de la variable
        debut = lecteur.entier64() if decalage64 else lecteur.entier()
        noms = tuple(noms_dimensions[i] for i in ids)
        enregistrement = bool(noms) and dimensions[noms[0]] == 0
        forme = tuple(enregistrements if enregistrement and k == 0 else dimensions[d]
                      for k, d in enumerate(noms))  # fmt: skip
        v = Variable(nom, noms, forme, attributs, type_nc, debut)
        fichier.variables[nom] = v
        if enregistrement:
            a_enregistrer.append((v, taille))
    # Une seule variable d'enregistrement : pas de bourrage entre enregistrements.
    pas = sum(t for _, t in a_enregistrer)
    if len(a_enregistrer) == 1:
        v = a_enregistrer[0][0]
        pas = _produit(v.forme[1:]) * v.taille_valeur
    for v, _ in a_enregistrer:
        v.pas_enregistrement = pas
    return fichier
