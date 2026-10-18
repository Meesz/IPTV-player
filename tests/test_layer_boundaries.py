"""Import-boundary checks for the layer rules in AGENTS.md.

Parses source with ``ast`` instead of importing modules, so it needs neither Qt nor libvlc.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PRESENTATION_DIRS = ("ui/widgets", "ui/windows", "ui/dialogs")
# The only presentation module allowed to reach into infra.
PRESENTATION_INFRA_ALLOWED = {"ui/widgets/player_widget.py": {"infra.playback.vlc_backend"}}
VLC_ALLOWED = {"infra/playback/vlc_backend.py"}
# Side-effect libraries presentation code must reach through infra.
PRESENTATION_FORBIDDEN = ("infra", "sqlite3", "requests")


def _python_files(*dirs: str) -> list[Path]:
    files = []
    for d in dirs:
        found = sorted((ROOT / d).rglob("*.py"))
        assert found, f"No Python files found under {d}; update the boundary test paths"
        files.extend(found)
    return files


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Resolve relative imports against the file's package.
                package = path.relative_to(ROOT).parent.parts
                base = package[: len(package) - (node.level - 1)]
                modules.add(".".join((*base, node.module) if node.module else base))
            elif node.module:
                modules.add(node.module)
    return modules


def _in_package(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_presentation_does_not_import_infra():
    violations = []
    for path in _python_files(*PRESENTATION_DIRS):
        allowed = PRESENTATION_INFRA_ALLOWED.get(_rel(path), set())
        for module in _imported_modules(path):
            if module not in allowed and any(_in_package(module, pkg) for pkg in PRESENTATION_FORBIDDEN):
                violations.append(f"{_rel(path)} imports {module}")
    assert not violations, "Presentation code must go through controllers/services:\n" + "\n".join(violations)


@pytest.mark.parametrize("layer", ["core", "infra"])
def test_lower_layers_do_not_import_ui(layer):
    violations = [
        f"{_rel(path)} imports {module}"
        for path in _python_files(layer)
        for module in _imported_modules(path)
        if _in_package(module, "ui")
    ]
    assert not violations, "\n".join(violations)


def test_vlc_is_only_imported_by_backend():
    violations = [
        f"{_rel(path)} imports {module}"
        for path in _python_files("app", "core", "infra", "ui")
        if _rel(path) not in VLC_ALLOWED
        for module in _imported_modules(path)
        if _in_package(module, "vlc")
    ]
    assert not violations, "Keep python-vlc behind infra/playback/vlc_backend.py:\n" + "\n".join(violations)
