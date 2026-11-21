"""La vitrine Neocities (vitrine/index.html) garde la direction artistique de l'appli."""

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
STYLE_APPLI = RACINE / "src" / "demographie" / "web" / "static" / "style.css"
VITRINE = RACINE / "vitrine" / "index.html"

BLOC_RACINE = re.compile(r"(:root[^{]*)\{([^{}]*)\}")
VARIABLE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def _palettes(css: str) -> dict[str, dict[str, str]]:
    """Variables CSS par sélecteur :root (clair, sombre automatique, sombre forcé)."""
    palettes: dict[str, dict[str, str]] = {}
    for selecteur, corps in BLOC_RACINE.findall(css):
        cle = " ".join(selecteur.split())
        palettes.setdefault(cle, {}).update(
            (nom, valeur.strip().lower()) for nom, valeur in VARIABLE.findall(corps)
        )
    return palettes


def test_vitrine_un_seul_fichier():
    html = VITRINE.read_text(encoding="utf-8")
    assert "<style>" in html
    assert 'rel="stylesheet"' not in html, "Neocities : tout doit tenir dans index.html"
    assert "<script" not in html


def test_vitrine_reprend_les_couleurs_de_l_appli():
    appli = _palettes(STYLE_APPLI.read_text(encoding="utf-8"))
    vitrine = _palettes(VITRINE.read_text(encoding="utf-8"))
    assert set(appli) == {
        ":root",
        ':root:not([data-theme="light"])',
        ':root[data-theme="dark"]',
    }
    for selecteur, variables in appli.items():
        for nom, valeur in variables.items():
            assert vitrine.get(selecteur, {}).get(nom) == valeur, (
                f"vitrine/index.html : {nom} ({selecteur}) doit valoir {valeur} comme dans "
                "style.css"
            )
