import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from mainuan_recursos.catalog import parse_catalog

NOW = datetime(2026, 10, 22, 15, tzinfo=timezone.utc)
HOSTS = ('mainuan.example',)


def catalog_dict():
    return json.loads((Path(__file__).resolve().parents[1] / 'examples/catalog.json').read_text())


def catalog():
    return parse_catalog(json.dumps(catalog_dict()).encode(), HOSTS, NOW)


def release():
    return catalog().releases[0]


def version(number='2.0.0', trust=True, arch='amd64'):
    return SimpleNamespace(version=number, architecture=arch, origins=[SimpleNamespace(trusted=trust)])


def package(installed=None, candidate='2.0.0', trust=True, hold=False, configured=True, arch='amd64'):
    current = version(installed, arch=arch) if installed else None
    available = version(candidate, trust, arch) if candidate else None
    return SimpleNamespace(installed=current, candidate=available, is_installed=bool(installed),
                           _pkg=SimpleNamespace(current_state=6 if configured else 4, selected_state=2 if hold else 1),
                           versions=[v for v in (current, available) if v])
