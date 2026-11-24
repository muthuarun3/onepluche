"""Appli 5, phase C : risques naturels (base GASPAR de Géorisques), dans stat.observation."""

import zipfile
from decimal import Decimal

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import config, db
from demographie.app import app
from demographie.imports import pipeline
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.connecteurs.gaspar import GASPAR, communes_cog
from demographie.imports.modele import Fichier, FichierIllisible, Referentiel

# L'archive de test ne garde que la Creuse, les Bouches-du-Rhône et La Réunion
# (tests/fixtures/reduire_gaspar.py) ; le Finistère n'y a aucune ligne.
REFERENTIEL = Referentiel(
    identifiants={}, region_du_departement={"23": "75", "13": "93", "974": "04", "29": "53"}
)


def _valeur(lignes, indicateur, code, annee, modalite=None):
    return next(
        x.valeur
        for x in lignes
        if x.indicateur == indicateur and x.code == code and x.periode.year == annee
        and (x.modalite[1] if x.modalite else None) == modalite
    )  # fmt: skip


def test_groupe_et_communes():
    assert GASPAR in CONNECTEURS["avenir"]
    cog = communes_cog()
    assert len(cog) == 34875 and "23096" in cog and "75056" in cog and "75101" not in cog


def test_lecture():
    lignes = list(GASPAR.lire(FIXTURES / "gaspar.zip", REFERENTIEL))
    # Creuse : les tempêtes de 1982 et de 1999 (inondations et tempête, ou mouvements de
    # terrain) ont touché ses 256 communes de l'époque, deux périls chacune.
    assert _valeur(lignes, "CATNAT_ARRETES", "23", 1982) == 512
    assert _valeur(lignes, "CATNAT_ARRETES", "23", 2019, "SECHERESSE") == 20
    totaux = [x for x in lignes if x.indicateur == "CATNAT_ARRETES" and x.code == "23"
              and x.modalite is None]  # fmt: skip
    assert sum(x.valeur for x in totaux) == 1096
    # Zéros publiés : le Finistère n'a aucune ligne dans l'archive réduite.
    assert _valeur(lignes, "CATNAT_ARRETES", "29", 1999) == 0
    # France = somme des départements ; métropole sans La Réunion.
    assert _valeur(lignes, "CATNAT_ARRETES", "FR", 1999) == sum(
        _valeur(lignes, "CATNAT_ARRETES", c, 1999) for c in ("23", "13", "974", "29")
    )
    # Les deux dernières années d'événement sont provisoires.
    statuts = {x.periode.year: x.statut for x in totaux}
    assert statuts[2025] == statuts[2024] == "PROVISOIRE" and statuts[2023] == "DEFINITIF"
    # Sécheresse : 32 des 255 communes actuelles de la Creuse reconnues de 2014 à 2023.
    assert _valeur(lignes, "CATNAT_SECHERESSE_10ANS", "23", 2023) == Decimal("12.55")
    assert _valeur(lignes, "CATNAT_SECHERESSE_10ANS", "974", 2023) == 0
    # Plans de prévention en vigueur : 31 communes de la Creuse, 79 % des Bouches-du-Rhône.
    assert _valeur(lignes, "COMMUNES_PPRN", "23", 2026) == Decimal("12.16")
    assert _valeur(lignes, "COMMUNES_PPRN", "13", 2026) == Decimal("78.99")


def test_peril_inconnu(tmp_path):
    chemin = tmp_path / "gaspar.zip"
    with zipfile.ZipFile(FIXTURES / "gaspar.zip") as source, zipfile.ZipFile(chemin, "w") as z:
        for nom in source.namelist():
            contenu = source.read(nom)
            if nom.startswith("catnat"):
                contenu += b"X;23096;Gueret;ZZZ;Inconnu;2020-01-01;2020-01-02;;;\n"
            z.writestr(nom, contenu)
    with pytest.raises(FichierIllisible, match="Péril inconnu « ZZZ »"):
        list(GASPAR.lire(chemin, REFERENTIEL))
    vide = tmp_path / "vide.zip"
    with zipfile.ZipFile(vide, "w") as z:
        z.writestr("autre.csv", b"a;b\n")
    with pytest.raises(FichierIllisible, match="catnat et pprn introuvables"):
        list(GASPAR.lire(vide, REFERENTIEL))


def test_import_et_pages(urls_module):
    chemin = FIXTURES / "gaspar.zip"
    fichier = Fichier(url=chemin.resolve().as_uri(), nom="gaspar.zip")
    with db.connexion("import") as conn:
        resultat = pipeline.importer(
            conn, GASPAR, fichier, config.charger().donnees_brutes, chemin_local=chemin
        )
    assert resultat.statut == "PUBLIE", resultat.message
    client = TestClient(app)
    vue = client.get("/avenir")
    assert vue.status_code == 200
    assert "Les catastrophes naturelles : France" in vue.text and 'id="catnat"' in vue.text
    fiche = client.get("/avenir/DEP/23")
    assert fiche.status_code == 200
    assert "1 096" in fiche.text  # reconnaissances depuis 1982
    assert "12,2 %" in fiche.text or "12,2 %" in fiche.text  # plans de prévention
    assert "Sécheresse (retrait-gonflement des argiles)" in fiche.text
    assert "Bientôt : catastrophes naturelles" not in fiche.text
