"""Consulta conservadora de atualizações dos pacotes de recursos do Mainuan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

CONFIG_FILE = Path('/etc/mainuan/atualizador-recursos.conf')
PACKAGE_NAME = re.compile(r'^[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?$')


@dataclass(frozen=True)
class ResourceUpdate:
    package: str
    installed: str
    candidate: str
    description: str = ''


def load_extra_packages(path: Path = CONFIG_FILE) -> set[str]:
    """Aceita apenas nomes literais de pacotes, nunca comandos ou padrões."""
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return set()
    entries = set()
    for line in lines:
        name = line.split('#', 1)[0].strip()
        if name and PACKAGE_NAME.fullmatch(name):
            entries.add(name)
    return entries


def scan_resources(cache=None, config_path: Path = CONFIG_FILE) -> list[ResourceUpdate]:
    """Usa exclusivamente os metadados confiáveis do APT local.

    Nenhum servidor GitHub é consultado e nenhuma instalação acontece aqui.
    """
    if cache is None:
        import apt  # pacote python3-apt do Ubuntu
        cache = apt.Cache()
    allowlist = load_extra_packages(config_path)
    result = []
    for pkg in cache:
        name = pkg.name
        if not (name.startswith('mainuan-') or name in allowlist):
            continue
        if not pkg.is_installed or not pkg.is_upgradable:
            continue
        if pkg.installed is None or pkg.candidate is None:
            continue
        result.append(ResourceUpdate(
            package=name,
            installed=pkg.installed.version,
            candidate=pkg.candidate.version,
            description=(pkg.candidate.summary or '').strip(),
        ))
    return sorted(result, key=lambda item: item.package)


def is_live_session() -> bool:
    """Evita notificações em instalações experimentadas por mídia Live."""
    for location in ('/run/casper', '/cdrom/casper', '/run/live/medium'):
        if Path(location).exists():
            return True
    try:
        tokens = Path('/proc/cmdline').read_text(encoding='utf-8').split()
    except OSError:
        return False
    return any(token in ('boot=casper', 'boot=live') for token in tokens)
