"""Accès réservé par lien secret : clé, cookie, exceptions, révocation."""

import pytest
from fastapi.testclient import TestClient

from demographie import acces
from demographie.app import app

CLE = "cle-de-test-0123456789"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(acces.VARIABLE, CLE)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def test_sans_cle_configuree_le_site_reste_ouvert(monkeypatch):
    monkeypatch.delenv(acces.VARIABLE, raising=False)
    assert TestClient(app).get("/mentions-inexistantes").status_code == 404


def test_sans_cookie_le_site_est_ferme(client):
    reponse = client.get("/")
    assert reponse.status_code == 403
    assert "Accès sur invitation" in reponse.text
    assert reponse.headers["Content-Security-Policy"].startswith("default-src 'self'")


def test_api_fermee_en_json(client):
    reponse = client.get("/api/v1/territoires")
    assert reponse.status_code == 401
    assert "lien d'invitation" in reponse.json()["detail"]
    assert client.get("/api/openapi.json").status_code == 401


def test_mauvaise_cle_refusee_sans_cookie(client):
    reponse = client.get("/", params={"cle": "mauvaise"})
    assert reponse.status_code == 403
    assert acces.COOKIE not in reponse.cookies


def test_bonne_cle_pose_le_cookie_et_nettoie_l_adresse(client):
    reponse = client.get("/besoins", params={"cle": CLE, "x": "1"})
    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/besoins?x=1"
    entete = reponse.headers["set-cookie"]
    assert CLE not in entete
    assert f"{acces.COOKIE}={acces.jeton(CLE)}" in entete
    for attribut in ("HttpOnly", "Secure", "SameSite=lax", f"Max-Age={acces.DUREE_COOKIE}"):
        assert attribut in entete


def test_cookie_valide_ouvre_le_site(client):
    client.get("/", params={"cle": CLE})
    # Route inexistante : 404 de l'appli, donc le contrôle d'accès est passé.
    assert client.get("/page-inexistante").status_code == 404


def test_changer_la_cle_revoque_les_cookies(client, monkeypatch):
    client.get("/", params={"cle": CLE})
    monkeypatch.setenv(acces.VARIABLE, "nouvelle-cle-0123456789")
    assert client.get("/page-inexistante").status_code == 403


@pytest.mark.parametrize("chemin", ["/sante", "/static/style.css"])
def test_chemins_publics(client, chemin):
    assert client.get(chemin).status_code == 200


def test_robots_interdit_tout(client):
    reponse = client.get("/robots.txt")
    assert reponse.status_code == 200
    assert "Disallow: /" in reponse.text
