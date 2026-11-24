"""Appli 5, phase B : climat (Banque mondiale, CMIP6 à 0,25°), publié dans stat.projection."""

import struct
from datetime import date

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import netcdf3, pipeline, telechargement
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs import climat as module_climat
from demographie.imports.connecteurs.climat import CLIMAT, mailles
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel
from demographie.web.avenir import ecart

NOM = "climat-cmip6-hd35-ssp585.csv"


def _nom(texte: str) -> bytes:
    brut = texte.encode()
    return struct.pack(">i", len(brut)) + brut + b"\0" * (-len(brut) % 4)


def _grille_nc(valeur) -> bytes:
    """Un NetCDF classique comme ceux de la Banque mondiale : lat, lon et une variable
    d'enregistrement « anomaly-hd35-annual-mean » (time, lat, lon) ; ``valeur(lat, lon)``."""
    nlat, nlon = 721, 1440
    lat = [-90 + 0.25 * i for i in range(nlat)]
    lon = [-180 + 0.25 * j for j in range(nlon)]
    remplissage = 1.0000000200408773e20

    def variables(debuts):
        def var(nom, dims, attributs, taille, debut):
            return (_nom(nom) + struct.pack(">i", len(dims))
                    + b"".join(struct.pack(">i", d) for d in dims) + attributs
                    + struct.pack(">iii", 5, taille, debut))  # fmt: skip

        sans = struct.pack(">ii", 0, 0)
        manquante = (struct.pack(">ii", 12, 1) + _nom("_FillValue")
                     + struct.pack(">iif", 5, 1, remplissage))  # fmt: skip
        return (struct.pack(">ii", 11, 3)
                + var("lat", [1], sans, 4 * nlat, debuts[0])
                + var("lon", [2], sans, 4 * nlon, debuts[1])
                + var("anomaly-hd35-annual-mean", [0, 1, 2], manquante, 4 * nlat * nlon,
                      debuts[2]))  # fmt: skip

    entete = (b"CDF\x01" + struct.pack(">i", 1) + struct.pack(">ii", 10, 3)
              + _nom("time") + struct.pack(">i", 0) + _nom("lat") + struct.pack(">i", nlat)
              + _nom("lon") + struct.pack(">i", nlon) + struct.pack(">ii", 0, 0))  # fmt: skip
    taille = len(entete) + len(variables((0, 0, 0)))
    debuts = (taille, taille + 4 * nlat, taille + 4 * nlat + 4 * nlon)
    donnees = [remplissage if valeur(a, o) is None else valeur(a, o) for a in lat for o in lon]
    axes = struct.pack(f">{nlat}f", *lat) + struct.pack(f">{nlon}f", *lon)
    return entete + variables(debuts) + axes + struct.pack(f">{nlat * nlon}f", *donnees)


def test_ecart():
    assert ecart(2.345, "degres_c") == "+2,3 °C"
    assert ecart(-12.4, "jours") == "−12 jours"
    assert ecart(0.6, "jours") == "+1 jour"
    assert ecart(None, "mm") == "—"


def test_groupe_et_mailles():
    assert CLIMAT in CONNECTEURS["avenir"]
    assert len(CLIMAT.fichiers()) == 21  # 7 variables × 3 scénarios
    assert CLIMAT.accepte(NOM) and not CLIMAT.accepte("climat-cmip6-txx-ssp585.csv")
    toutes = mailles()
    assert len(toutes) == 96
    surface = sum(km2 for liste in toutes.values() for _, _, km2 in liste)
    assert 540_000 < surface < 560_000  # la métropole fait environ 550 000 km²
    assert 95 < sum(km2 for _, _, km2 in toutes["75"]) < 115  # Paris : 105 km²


def test_netcdf_et_grille(monkeypatch):
    # Valeur = latitude (lisible), sauf une maille « en mer » sans valeur.
    contenu = _grille_nc(lambda a, o: None if (a, o) == (43.25, 5.25) else a)
    fichier = netcdf3.lire_octets(contenu)
    v = fichier.variables["anomaly-hd35-annual-mean"]
    assert v.forme == (1, 721, 1440) and v.pas_enregistrement == 721 * 1440 * 4
    assert fichier.ligne("anomaly-hd35-annual-mean", 0, 4)[0] == -89.0
    lectures = []

    def plage(url, debut, fin):
        lectures.append(fin - debut + 1)
        return contenu[debut : fin + 1]

    monkeypatch.setattr(telechargement, "lire_plage", plage)
    grille = module_climat._grille_france("https://exemple.invalid/a.nc")
    assert grille[(48.75, 2.25)] == 48.75 and grille[(43.25, 5.25)] is None
    # Seules les lignes de la métropole sont lues, pas les 4 Mo de la grille.
    assert max(lectures) < 400_000
    # Un fichier NetCDF-4 (HDF5) arrête l'import au lieu d'être lu de travers.
    contenu = b"\x89HDF\r\n\x1a\n" + bytes(200)
    with pytest.raises(FichierIllisible, match="HDF5"):
        module_climat._grille_france("https://exemple.invalid/b.nc")


def test_lecture():
    lignes = list(CLIMAT.lire(FIXTURES / NOM, Referentiel(identifiants={})))
    assert {p.indicateur for p in lignes} == {"CLIM_HD35"}
    assert {p.scenario for p in lignes} == {"GIEC_SSP585"}
    assert len({p.code for p in lignes}) == 97  # 96 départements et la métropole
    assert {(p.periode, p.periode_fin) for p in lignes} >= {(date(2080, 1, 1), date(2099, 12, 31))}

    def valeur(code, statistique, annee=2080):
        return next(p.valeur for p in lignes if p.code == code and p.statistique == statistique
                    and p.periode.year == annee)  # fmt: skip

    # Bouches-du-Rhône : 47 jours à 35 °C ou plus en plus en fin de siècle ; Finistère : 0.
    assert valeur("13", "MEDIANE") == pytest.approx(47.13)
    assert valeur("29", "MEDIANE") == 0
    assert valeur("13", "BAS") <= valeur("13", "MEDIANE") <= valeur("13", "HAUT")
    assert 15 < valeur("FM", "MEDIANE") < 20


def test_import_et_pages(urls_module):
    chemin = FIXTURES / NOM
    fichier = Fichier(url=chemin.resolve().as_uri(), nom=NOM)
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, CLIMAT, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )
    assert resultat.statut == "PUBLIE", resultat.message
    client = TestClient(app)
    vue = client.get("/avenir")
    assert vue.status_code == 200
    # Seul SSP5-8.5 est importé ici : la page s'y range au lieu du scénario par défaut.
    assert "Le climat d'ici la fin du siècle" in vue.text and "SSP5-8.5" in vue.text
    assert "au-dessus de 35 °C" in vue.text
    fiche = client.get("/avenir/DEP/13", params={"climat": "GIEC_SSP585"})
    assert fiche.status_code == 200
    assert "+47 jours" in fiche.text and "France +18 jours" in fiche.text
    assert client.get("/avenir", params={"climat": "RCP45"}).status_code == 422
    params = {"indicateur": "CLIM_HD35", "niveau": "DEP", "code": "13",
              "scenario": "GIEC_SSP585"}  # fmt: skip
    api = client.get("/api/v1/projections", params=params)
    assert api.status_code == 200
    assert {v["statistique"] for v in api.json()["valeurs"]} == {"BAS", "MEDIANE", "HAUT"}
