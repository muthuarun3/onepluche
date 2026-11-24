"""Veille des programmes : empreinte, copie, changement détecté, erreur signalée sans effacer."""

import io
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demographie import alertes, cli, db
from demographie.app import app
from demographie.imports import veille_programmes

URL = "https://exemple.invalid/alpha/programme.pdf"
SUIVIS = f"""
[[suivis]]
candidat = "alpha-camille"
version = "v1"
url = "{URL}"
"""


@pytest.fixture
def election(tmp_path: Path) -> Path:
    dossier = tmp_path / "programmes" / "2027"
    dossier.mkdir(parents=True)
    (dossier / "suivis.toml").write_text(SUIVIS, encoding="utf-8")
    return dossier


class FauxSite:
    """Sert le contenu courant ; ``None`` = erreur 404."""

    def __init__(self, contenu: bytes | None):
        self.contenu = contenu

    def __call__(self, url: str, dossier: Path) -> Path:
        if self.contenu is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO())
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / "telechargement.part"
        chemin.write_bytes(self.contenu)
        return chemin


def test_suivis_du_depot_valides():
    racine = Path(__file__).resolve().parents[1]
    veille_programmes.lire_suivis(racine / "programmes" / "2027")


def test_suivi_invalide_refuse(election):
    (election / "suivis.toml").write_text(SUIVIS.replace("https://", "http://"))
    with pytest.raises(ValueError, match="url"):
        veille_programmes.lire_suivis(election)


def test_changement_detecte_puis_erreur(urls_db, election, tmp_path):
    copies = tmp_path / "copies"
    site = FauxSite(b"version 1")
    with db.connexion("import") as conn:
        premier = veille_programmes.veiller(conn, election, copies, site)
        deuxieme = veille_programmes.veiller(conn, election, copies, site)
        site.contenu = b"version 1, page 4 corrigee"
        troisieme = veille_programmes.veiller(conn, election, copies, site)
        site.contenu = None
        quatrieme = veille_programmes.veiller(conn, election, copies, site)
    # Premier relevé : rien à comparer ; même texte : inchangé ; autre texte : modifié.
    assert [r.change for r in (premier[0], deuxieme[0], troisieme[0])] == [False, False, True]
    assert premier[0].sha256 == deuxieme[0].sha256 != troisieme[0].sha256
    # Deux copies distinctes, rangées sous leur empreinte, aucun doublon ni fichier en cours.
    gardees = sorted(p.name for p in (copies / "2027" / "alpha-camille").iterdir())
    assert gardees == sorted(f"v1-{r.sha256}.pdf" for r in (premier[0], troisieme[0]))
    assert not any((copies / ".en-cours").iterdir())
    # Page disparue : signalée, rien d'effacé ; le relevé suivant compare au dernier texte lu.
    assert quatrieme[0].en_erreur and "404" in quatrieme[0].message
    assert len(gardees) == 2
    site.contenu = b"version 1, page 4 corrigee"
    with db.connexion("import") as conn:
        cinquieme = veille_programmes.veiller(conn, election, copies, site)
    assert cinquieme[0].change is False

    # La page « Sources » montre le dernier relevé de chaque adresse suivie.
    page = TestClient(app).get("/sources").text
    assert "Programmes présidentiels suivis" in page and "alpha-camille" in page
    assert "Inchangé depuis le" in page


def test_commande_alerte_si_modifie(urls_db, election, tmp_path, monkeypatch):
    envois = []
    monkeypatch.setattr(alertes, "signaler", lambda url, etat, resume="": envois.append(etat))
    # Adresse propre à ce test : la base est partagée avec le test précédent.
    suivis = election / "suivis.toml"
    suivis.write_text(suivis.read_text().replace("programme.pdf", "commande.pdf"))
    monkeypatch.setenv("DEMO_PROGRAMMES", str(election.parent))
    monkeypatch.setenv("DEMO_PING_PROGRAMMES", "https://hc-ping.com/programmes")
    site = FauxSite(b"texte A")
    monkeypatch.setattr(veille_programmes.telechargement, "telecharger", site)
    assert cli.main(["veiller", "programmes"]) == 0
    site.contenu = b"texte B"
    assert cli.main(["veiller", "programmes"]) == 0
    site.contenu = None
    assert cli.main(["veiller", "programmes"]) == 1
    assert envois == ["debut", "succes", "debut", "echec", "debut", "echec"]
