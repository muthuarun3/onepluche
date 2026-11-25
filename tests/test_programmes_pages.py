"""Pages et API « Programmes » avec les deux fiches fictives ; neutralité des gabarits."""

import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demographie.app import app
from demographie.donnees import programmes
from demographie.web import programmes as pages_programmes

RACINE = Path(__file__).resolve().parents[1]
GABARITS = RACINE / "src" / "demographie" / "web" / "templates"
STYLE = RACINE / "src" / "demographie" / "web" / "static" / "style.css"
FIXTURES = Path(__file__).parent / "fixtures" / "programmes"


@pytest.fixture
def client(urls_db, tmp_path, monkeypatch):
    election = tmp_path / "programmes" / "2027"
    election.mkdir(parents=True)
    shutil.copy(RACINE / "programmes" / "2027" / "sujets.toml", election)
    for fiche in FIXTURES.glob("*.toml"):
        shutil.copy(fiche, election)
    monkeypatch.setenv("DEMO_PROGRAMMES", str(election.parent))
    programmes.election.cache_clear()
    yield TestClient(app)
    programmes.election.cache_clear()


def test_liste_des_candidats(client):
    page = client.get("/programmes")
    assert page.status_code == 200
    texte = page.text
    assert "premier tour le 18 avril 2027" in texte
    assert "2 candidats ont" in texte
    # Ordre alphabétique par nom de famille.
    assert texte.index("Camille Alpha") < texte.index("Dominique Bravo")
    assert "2 mesures sur\n        2 sujets (sur 12)" in texte
    assert "Candidature déclarée" in texte
    assert '<a href="/programmes" aria-current="page">Les candidats</a>' in texte


def test_fiche_candidat(client):
    texte = client.get("/programmes/alpha-camille").text
    assert "« Nous fixerons l&#39;âge légal de départ à 63 ans. »" in texte
    assert (
        'href="https://exemple.invalid/alpha/programme-v1.pdf" rel="noopener">page 4</a>' in texte
    )
    # Coût annoncé et chiffrage indépendant, en toutes lettres.
    assert "5 milliards d&#39;euros par an" in texte and "7 milliards d&#39;euros par an" in texte
    # Mesure retirée : visible, barrée, avec la date de la version qui l'a retirée.
    assert "<del>Construction de 400 000 logements par an</del>" in texte
    assert "Retirée dans la version du 15 novembre 2026." in texte
    # Sommaire : « pas de proposition » déduit ; logement à 0 mesure en vigueur.
    assert (
        '<a href="#logement">Logement</a> :\n      <span class="muet">pas de proposition</span>'
        in texte
    )
    # Contexte chiffré : indicateur connu, sans valeur France dans la base de test.
    assert "Part des 60 ans et plus" in texte
    assert "pas de valeur pour la France entière" in texte
    assert "Versions précédentes (1)" in texte
    assert '<a href="/programmes" aria-current="page">Les candidats</a>' in texte
    assert client.get("/programmes/inconnu-x").status_code == 404
    assert client.get("/programmes/Pas_Valide").status_code == 422


def test_comparer(client):
    texte = client.get("/programmes/comparer?sujet=retraites").text
    assert "Âge légal de départ à la retraite" in texte
    assert re.search(r"Camille Alpha</span>.*?63 ans", texte, re.S)
    assert re.search(r"Dominique Bravo</span>.*?65 ans", texte, re.S)
    assert '<a href="/programmes/comparer" aria-current="page">' in texte
    sante = client.get("/programmes/comparer?sujet=sante").text
    assert "Un centre de santé par canton" in sante
    assert sante.count("Pas de proposition") == 1  # Bravo n'en dit rien
    # Sans sujet : le premier de la grille ; sujet inconnu : 404.
    assert "Emploi et travail" in client.get("/programmes/comparer").text
    assert client.get("/programmes/comparer?sujet=loisirs").status_code == 404


def test_api(client):
    liste = client.get("/api/v1/programmes").json()
    assert [c["id"] for c in liste["candidats"]] == ["alpha-camille", "bravo-dominique"]
    assert len(liste["grille"]["sujets"]) == 12
    fiche = client.get("/api/v1/programmes/alpha-camille").json()
    assert fiche["mesures"][0]["citation"].startswith("Nous fixerons")
    assert client.get("/api/v1/programmes/inconnu-x").status_code == 404


def test_accueil_et_barre_laterale(client):
    texte = client.get("/").text
    assert '<p class="categorie-menu" id="menu-programmes">Programmes</p>' in texte
    assert 'href="/programmes/comparer"' in texte and "Les candidats" in texte


def test_aucun_programme(urls_db, tmp_path, monkeypatch):
    election = tmp_path / "programmes" / "2027"
    election.mkdir(parents=True)
    shutil.copy(RACINE / "programmes" / "2027" / "sujets.toml", election)
    monkeypatch.setenv("DEMO_PROGRAMMES", str(election.parent))
    programmes.election.cache_clear()
    try:
        client = TestClient(app)
        assert "Aucun programme n'est encore analysé" in client.get("/programmes").text
        assert "Aucun programme n'est encore analysé" in client.get("/programmes/comparer").text
    finally:
        programmes.election.cache_clear()


def test_gabarits_neutres():
    fichiers = sorted(GABARITS.glob("*programmes*.html"))
    assert len(fichiers) == 4
    for fichier in fichiers:
        assert not programmes.mots_de_jugement(fichier.read_text(encoding="utf-8")), fichier.name
    for libelle in pages_programmes.STATUTS.values():
        assert not programmes.mots_de_jugement(libelle)


def test_une_seule_couleur():
    """Le bloc de style « Programmes » n'introduit aucune couleur : seulement les variables."""
    css = STYLE.read_text(encoding="utf-8")
    bloc = css[css.index("/* Programmes :") :]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb|hsl", bloc)
