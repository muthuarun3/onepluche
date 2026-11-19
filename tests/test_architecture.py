"""Vérifie les règles entre modules (dossier de conception, étape 7)."""

import ast
import re
from pathlib import Path

import pytest

PAQUET = Path(__file__).resolve().parents[1] / "src" / "demographie"

# Pour chaque module : les modules internes qu'il n'a pas le droit d'importer.
INTERDITS = {
    "catalogue": {"db", "config", "imports", "donnees", "api", "web", "app", "migrations"},
    "imports": {"donnees", "api", "web", "app"},
    "donnees": {"imports", "api", "web", "app", "migrations"},
    "api": {"db", "config", "imports", "web", "app", "migrations"},
    "web": {"db", "config", "imports", "api", "app", "migrations"},
}
SQL_ECRIT = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b\s", re.IGNORECASE)


def _imports_internes(fichier: Path) -> set[str]:
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            if noeud.module == "demographie":
                noms.update(a.name for a in noeud.names)
            elif noeud.module.startswith("demographie."):
                noms.add(noeud.module.split(".")[1])
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.startswith("demographie."):
                    noms.add(alias.name.split(".")[1])
    return noms


@pytest.mark.parametrize("module", sorted(INTERDITS))
def test_dependances_entre_modules(module):
    violations = []
    for fichier in (PAQUET / module).rglob("*.py"):
        interdits = _imports_internes(fichier) & INTERDITS[module]
        if interdits:
            violations.append(f"{fichier.relative_to(PAQUET)} importe {sorted(interdits)}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("module", ["api", "web"])
def test_pas_de_sql_dans_api_et_web(module):
    fautifs = [
        str(f.relative_to(PAQUET))
        for f in (PAQUET / module).rglob("*")
        if f.suffix in {".py", ".sql"} and (f.suffix == ".sql" or SQL_ECRIT.search(f.read_text()))
    ]
    assert not fautifs, f"SQL trouvé dans : {fautifs}"
