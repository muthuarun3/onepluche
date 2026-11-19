"""Alertes par battement et page d'état des sources."""

import pytest
from conftest import FIXTURES
from fastapi.testclient import TestClient

from demographie import alertes, cli
from demographie.app import app

client = TestClient(app)


class _Reponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def envois(monkeypatch):
    recus = []

    def faux_urlopen(requete, timeout):
        recus.append((requete.full_url, requete.data.decode()))
        return _Reponse()

    monkeypatch.setattr(alertes.urllib.request, "urlopen", faux_urlopen)
    return recus


def test_sans_url_rien_n_est_envoye(envois):
    assert alertes.signaler(None, "echec", "x") is False
    assert envois == []


def test_url_https_obligatoire():
    with pytest.raises(ValueError):
        alertes.signaler("http://hc-ping.com/abc", "succes")


def test_reseau_indisponible_n_interrompt_rien(monkeypatch):
    def panne(*_args, **_kwargs):
        raise OSError("réseau coupé")

    monkeypatch.setattr(alertes.urllib.request, "urlopen", panne)
    assert alertes.signaler("https://hc-ping.com/abc", "succes") is False


def test_import_signale_debut_et_resultat(urls_module, monkeypatch, envois):
    monkeypatch.setenv("DEMO_PING_IMPORT", "https://hc-ping.com/abc")
    fichier = FIXTURES / "estim-pop-dep-sexe-aq-1975-2026.xlsx"
    assert cli.main(["importer", "estimations", "--fichier", str(fichier)]) == 0
    assert [url for url, _ in envois] == [
        "https://hc-ping.com/abc/start",
        "https://hc-ping.com/abc",
    ]
    assert "PUBLIE" in envois[-1][1]


def test_echec_signale(urls_module, monkeypatch, envois, tmp_path):
    monkeypatch.setenv("DEMO_PING_IMPORT", "https://hc-ping.com/abc")
    faux = tmp_path / "DS_NAISSANCES_FECONDITE_SERIES.zip"
    faux.write_bytes(b"pas une archive")
    assert cli.main(["importer", "etat-civil", "--fichier", str(faux)]) == 1
    url, corps = envois[-1]
    assert url == "https://hc-ping.com/abc/fail" and "REJETE" in corps


def test_etat_des_sources(urls_module):
    etat = client.get("/api/v1/sources").json()
    estimations = [e for e in etat if e["fichier_nom"] == "estim-pop-dep-sexe-aq-1975-2026.xlsx"]
    assert estimations[0]["dernier_statut"] == "PUBLIE"
    assert estimations[0]["derniere_publication"] is not None
    naissances = [e for e in etat if e["fichier_nom"] == "DS_NAISSANCES_FECONDITE_SERIES.zip"]
    assert naissances[0]["dernier_statut"] == "REJETE"
    assert naissances[0]["derniere_publication"] is None
    # Une source jamais importée apparaît quand même.
    assert any(e["source"] == "DREES_PENS" and e["fichier_nom"] is None for e in etat)
    page = client.get("/sources")
    assert page.status_code == 200 and "Dernier fichier rejeté" in page.text
