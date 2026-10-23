"""Identificação positiva de sessão Live, sem confundir mídia montada com boot."""
from enum import Enum
from pathlib import Path
import subprocess


# Pares explícitos: a versão comercial Mainuan não é uma versão do Ubuntu.
# VERSION/PRETTY_NAME (RC1 ou final) não participam da decisão.
SUPPORTED_SYSTEMS = {
    ('ubuntu', '26.04'): ('ubuntu', '26.04'),
    ('ubuntu', '2026'): ('ubuntu', '26.04'),
    ('mainuan', '26.04'): ('ubuntu', '26.04'),
    ('mainuan', '2026'): ('ubuntu', '26.04'),
    ('mainuan', '2027.1'): ('ubuntu', '26.04'),
}


def base_identity(system):
    """Base conhecida de uma identificação suportada; indícios contrários bloqueiam."""
    base = SUPPORTED_SYSTEMS.get((system.get('distro_id'), system.get('version_id')))
    if base is None:
        return None
    if system.get('ubuntu_codename', '') not in ('', 'resolute'):
        return None
    if system.get('base_id', base[0]) != base[0] or system.get('base_version_id', base[1]) != base[1]:
        return None
    return base


def supported_system(system):
    return base_identity(system) is not None


def system_compatibility(architectures=None):
    """Filtros das novidades; supported_system também valida os pares, sem produto cartesiano."""
    result = {'distro_id': sorted({pair[0] for pair in SUPPORTED_SYSTEMS}),
              'version_id': sorted({pair[1] for pair in SUPPORTED_SYSTEMS})}
    if architectures is not None:
        result['architecture'] = list(architectures)
    return result


class SessionKind(Enum):
    INSTALLED = 'installed'
    LIVE = 'live'
    UNKNOWN = 'unknown'


def session_kind():
    try:
        tokens = Path('/proc/cmdline').read_text().split()
    except OSError:
        tokens = None
    if tokens is not None and any(token in ('boot=casper', 'boot=live') for token in tokens):
        return SessionKind.LIVE
    try:
        mounts = []
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            left, right = line.split(' - ', 1)
            mounts.append((left.split()[4], right.split()[0]))
    except (OSError, ValueError, IndexError):
        mounts = []
    root_type = next((fs for mount, fs in mounts if mount == '/'), None)
    # /cdrom/casper sozinho pode pertencer a uma mídia montada após o login.
    # Só o root overlay com evidência ativa do ambiente Live justifica o fallback.
    live_root = any(fs == 'squashfs' and (mount == '/rofs' or mount.startswith(
        ('/run/live/rootfs/', '/lib/live/mount/rootfs/'))) for mount, fs in mounts)
    live_runtime = any(Path(p).exists() for p in ('/run/casper', '/run/live/medium'))
    if root_type == 'overlay' and (live_root or live_runtime):
        return SessionKind.LIVE
    if root_type and root_type not in ('overlay', 'squashfs', 'tmpfs'):
        return SessionKind.INSTALLED
    if tokens is not None and any(token.startswith('root=') for token in tokens) and not live_runtime:
        return SessionKind.INSTALLED
    return SessionKind.UNKNOWN


def is_live_session():
    """Compatibilidade de leitura: UNKNOWN não é falsamente chamado de Live."""
    return session_kind() == SessionKind.LIVE


def system_identity():
    import platform
    info = platform.freedesktop_os_release()
    architecture = subprocess.run(['/usr/bin/dpkg', '--print-architecture'], capture_output=True,
                                  text=True, check=True, timeout=5).stdout.strip()
    system = {'distro_id': info.get('ID', ''), 'version_id': info.get('VERSION_ID', ''),
              'architecture': architecture}
    if info.get('UBUNTU_CODENAME'):
        system['ubuntu_codename'] = info['UBUNTU_CODENAME']
    base = base_identity(system)
    if base:
        system.update(base_id=base[0], base_version_id=base[1])
    return system
