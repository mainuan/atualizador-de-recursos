"""Planejamento com metadados APT somente leitura e comparação Debian."""
from dataclasses import dataclass
from functools import cache


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
        return tuple(r for r in self.rows if r.status in ('Instalar', 'Atualizar'))

    @property
    def blockers(self):
        return tuple(r for r in self.rows if r.status not in ('Instalar', 'Atualizar', 'Já recebido'))

    @property
    def complete(self):
        return bool(self.rows) and all(r.status == 'Já recebido' for r in self.rows)


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
            rows.append(PackageRow(name, minimum, '', '', '', 'Indisponível nos repositórios'))
            continue
        pkg = cache[name]
        installed, candidate = pkg.installed, pkg.candidate
        current = installed.version if installed else ''
        available = candidate.version if candidate else ''
        architecture = candidate.architecture if candidate else ''
        if installed and configured(pkg) and version_compare(current, minimum) >= 0:
            status = 'Já recebido'
        elif installed and not configured(pkg):
            status = 'Pacote com configuração incompleta'
        elif getattr(pkg._pkg, 'selected_state', 0) == 2:  # apt_pkg.SELSTATE_HOLD
            status = 'Pacote retido pelo administrador'
        elif requested.sha256:
            # Catálogo automático aprova bytes e versão exatos. Nunca substituir
            # silenciosamente pela versão mais nova que aparecer no APT.
            if not candidate or available != minimum or architecture != requested.architecture:
                status = 'Candidato APT difere da versão aprovada'
            elif not trusted(candidate):
                status = 'Origem não confiável'
            elif getattr(candidate, 'sha256', '') != requested.sha256:
                status = 'Integridade do pacote aprovado divergente'
            else:
                status = 'Atualizar' if installed else 'Instalar'
        elif not candidate or version_compare(available, minimum) < 0:
            status = 'Versão necessária indisponível'
        elif installed and version_compare(available, current) <= 0:
            status = 'Sem atualização segura disponível'
        elif not trusted(candidate):
            status = 'Origem não confiável'
        else:
            status = 'Atualizar' if installed else 'Instalar'
        rows.append(PackageRow(name, minimum, current, available, architecture, status, requested.sha256))
    return Plan(tuple(rows))


def identity(package_id):
    parts = package_id.split(';')
    if len(parts) != 4 or not all(parts[:3]):
        raise PlanningError('O PackageKit retornou um identificador inválido.')
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
            raise PlanningError('A operação exige remoção, reinstalação, downgrade ou efeito não permitido.')
        name, version, arch = identity(package_id)
        identities.add((name, version, arch))
        if name not in cache:
            raise PlanningError(f'Não foi possível validar a origem de {name}.')
        pkg = cache[f'{name}:{arch}'] if f'{name}:{arch}' in cache else cache[name]
        matches = [v for v in pkg.versions if v.version == version and v.architecture == arch]
        if not matches or not any(trusted(v) for v in matches):
            raise PlanningError(f'O pacote {name} não possui uma origem confiável.')
        if pins and (name, version, arch) in pins:
            approved = pins[(name, version, arch)]
            if not all(getattr(v, 'sha256', '') == approved for v in matches if trusted(v)):
                raise PlanningError(f'A integridade do pacote aprovado {name} mudou. Verifique os repositórios.')
        if pkg._pkg.selected_state == 2:
            raise PlanningError(f'O pacote {name} está retido pelo administrador.')
        if pkg.installed and not configured(pkg):
            raise PlanningError(f'O pacote {name} está com configuração incompleta.')
        installed = pkg.installed.version if pkg.installed else ''
        if installed and version_compare(version, installed) <= 0:
            raise PlanningError(f'Reinstalação ou downgrade de {name} bloqueado.')
        evidence.append((info, package_id, installed))
    if not set(expected) <= identities:
        raise PlanningError('A simulação não confirmou todos os pacotes solicitados.')
    return tuple(sorted(evidence))
