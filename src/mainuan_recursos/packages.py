"""Planejamento com metadados APT somente leitura e comparação Debian."""
from dataclasses import dataclass
from functools import cache

from .i18n import _, pgettext

# Stable status codes used by the planning logic.  Every other status is a
# translated, human-readable reason that blocks the installation.
INSTALL = 'install'
UPGRADE = 'upgrade'
RECEIVED = 'received'


def status_text(status):
    """Human-readable label of a package status (codes are never shown raw)."""
    labels = {INSTALL: pgettext('package status', 'Install'),
              UPGRADE: pgettext('package status', 'Update'),
              RECEIVED: pgettext('package status', 'Already received')}
    return labels.get(status, status)


class PlanningError(ValueError):
    pass


@dataclass(frozen=True)
class PackageRow:
    name: str
    minimum: str
    installed: str
    candidate: str
    architecture: str
    status: str
    sha256: str = ''

    @property
    def identity(self):
        return (self.name, self.candidate, self.architecture)


@dataclass(frozen=True)
class Plan:
    rows: tuple[PackageRow, ...]

    @property
    def pending(self):
        return tuple(r for r in self.rows if r.status in (INSTALL, UPGRADE))

    @property
    def blockers(self):
        return tuple(r for r in self.rows if r.status not in (INSTALL, UPGRADE, RECEIVED))

    @property
    def complete(self):
        return bool(self.rows) and all(r.status == RECEIVED for r in self.rows)


@cache
def _comparator():
    import apt_pkg
    apt_pkg.init_system()
    return apt_pkg.version_compare


def version_compare(a, b):
    return _comparator()(a, b)


def configured(pkg):
    import apt_pkg
    return pkg.is_installed and pkg._pkg.current_state == apt_pkg.CURSTATE_INSTALLED


def trusted(version):
    return any(origin.trusted for origin in version.origins)


def build_plan(release, cache=None):
    if cache is None:
        import apt
        cache = apt.Cache()
    rows = []
    for requested in release.packages:
        name, minimum = requested.name, requested.min_version
        if name not in cache:
            rows.append(PackageRow(name, minimum, '', '', '', _('Unavailable in the repositories')))
            continue
        pkg = cache[name]
        installed, candidate = pkg.installed, pkg.candidate
        current = installed.version if installed else ''
        available = candidate.version if candidate else ''
        architecture = candidate.architecture if candidate else ''
        if installed and configured(pkg) and version_compare(current, minimum) >= 0:
            status = RECEIVED
        elif installed and not configured(pkg):
            status = _('Package with incomplete configuration')
        elif getattr(pkg._pkg, 'selected_state', 0) == 2:  # apt_pkg.SELSTATE_HOLD
            status = _('Package held by the administrator')
        elif requested.sha256:
            # Catálogo automático aprova bytes e versão exatos. Nunca substituir
            # silenciosamente pela versão mais nova que aparecer no APT.
            if not candidate or available != minimum or architecture != requested.architecture:
                status = _('APT candidate differs from the approved version')
            elif not trusted(candidate):
                status = _('Untrusted source')
            elif getattr(candidate, 'sha256', '') != requested.sha256:
                status = _('Integrity of the approved package does not match')
            else:
                status = UPGRADE if installed else INSTALL
        elif not candidate or version_compare(available, minimum) < 0:
            status = _('Required version unavailable')
        elif installed and version_compare(available, current) <= 0:
            status = _('No safe update available')
        elif not trusted(candidate):
            status = _('Untrusted source')
        else:
            status = UPGRADE if installed else INSTALL
        rows.append(PackageRow(name, minimum, current, available, architecture, status, requested.sha256))
    return Plan(tuple(rows))


def identity(package_id):
    parts = package_id.split(';')
    if len(parts) != 4 or not all(parts[:3]):
        raise PlanningError(_('PackageKit returned an invalid identifier.'))
    return tuple(parts[:3])


def validate_effects(effects, expected, cache=None, pins=None):
    """Verifica TODOS os efeitos simulados, inclusive dependências."""
    if cache is None:
        import apt
        cache = apt.Cache()
    identities = set()
    evidence = []
    for info, package_id in effects:
        # PK_INFO_ENUM_INSTALLING / UPDATING. Demais efeitos falham fechados.
        if info not in (11, 12):
            raise PlanningError(_('The operation requires removal, reinstallation, downgrade or a disallowed effect.'))
        name, version, arch = identity(package_id)
        identities.add((name, version, arch))
        if name not in cache:
            raise PlanningError(_('Could not validate the source of {name}.').format(name=name))
        pkg = cache[f'{name}:{arch}'] if f'{name}:{arch}' in cache else cache[name]
        matches = [v for v in pkg.versions if v.version == version and v.architecture == arch]
        if not matches or not any(trusted(v) for v in matches):
            raise PlanningError(_('The package {name} does not have a trusted source.').format(name=name))
        if pins and (name, version, arch) in pins:
            approved = pins[(name, version, arch)]
            if not all(getattr(v, 'sha256', '') == approved for v in matches if trusted(v)):
                raise PlanningError(_('The integrity of the approved package {name} has changed. Check the repositories.').format(name=name))
        if pkg._pkg.selected_state == 2:
            raise PlanningError(_('The package {name} is held by the administrator.').format(name=name))
        if pkg.installed and not configured(pkg):
            raise PlanningError(_('The package {name} has an incomplete configuration.').format(name=name))
        installed = pkg.installed.version if pkg.installed else ''
        if installed and version_compare(version, installed) <= 0:
            raise PlanningError(_('Reinstallation or downgrade of {name} blocked.').format(name=name))
        evidence.append((info, package_id, installed))
    if not set(expected) <= identities:
        raise PlanningError(_('The simulation did not confirm all requested packages.'))
    return tuple(sorted(evidence))
