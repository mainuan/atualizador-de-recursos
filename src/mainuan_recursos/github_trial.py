"""Ensaio GitHub opt-in: uma release examinada, sem catálogo/APT de produção."""
from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import ssl

from PyQt6 import QtDBus

from . import __version__
from .catalog import Catalog, CatalogError, Feature, Package, Release, decode
from .controller import Controller
from .packagekit import Transaction, ROOT, SERVICE, PROPERTIES
from .packages import PackageRow, Plan, PlanningError, configured, identity, version_compare
from .session import SessionKind, session_kind, system_identity

REPOSITORY = 'mainuan-gestao-drivers'
NAME = 'mainuan-gestao-drivers'
VERSION = '1.0'
SHA256 = 'd7a1c98743a204f6b5770c7746cb02b3b4d66c09d2d368966118ac39fa47b912'
SIZE = 190846
RELEASE_ID = 421218277
ASSET_ID = 667222935
RELEASE_URL = 'https://github.com/mainuan/mainuan-gestao-drivers/releases/tag/v1.0'
ASSET_URL = 'https://github.com/mainuan/mainuan-gestao-drivers/releases/download/v1.0/mainuan-gestao-drivers_1.0_all.deb'


def require(condition, message):
    if not condition:
        raise CatalogError(message)


def check_vm():
    result = subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True, text=True, timeout=5)
    require(result.returncode == 0, 'A homologação GitHub é exclusiva de uma VM com snapshot; use o modo normal neste computador.')
    require(os.geteuid() != 0, 'Abra a homologação como usuário comum, sem sudo.')
    require(session_kind() == SessionKind.INSTALLED, 'A homologação exige uma instalação normal, fora da sessão Live.')
    system = system_identity()
    require(system['distro_id'] in ('ubuntu', 'mainuan') and system['version_id'] in ('2026', '26.04'),
            'Este ensaio é destinado ao Mainuan 2026/Kubuntu 26.04.')


def check_url(url, binary=False):
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username
            and not parsed.password and not parsed.fragment, 'URL de homologação inválida.')
    allowed = ((parsed.hostname == 'api.github.com' and parsed.path.startswith('/repos/mainuan/'))
               or (parsed.hostname == 'raw.githubusercontent.com'
                   and parsed.path.startswith('/mainuan/atualizadorderecursos/')))
    if binary:
        allowed = allowed or (parsed.hostname == 'github.com' and parsed.path.startswith('/mainuan/mainuan-gestao-drivers/releases/download/'))
        allowed = allowed or parsed.hostname in ('release-assets.githubusercontent.com', 'objects.githubusercontent.com')
    require(allowed, 'Redirecionamento fora da infraestrutura autorizada do GitHub.')


class Redirects(HTTPRedirectHandler):
    def __init__(self, binary):
        super().__init__()
        self.binary = binary

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, self.binary)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, limit=1024 * 1024, binary=False, progress=None):
    check_url(url, binary)
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), Redirects(binary))
    with opener.open(Request(url, headers={'User-Agent': f'Mainuan-Recursos-Homologacao/{__version__}',
                                         'Accept': 'application/octet-stream' if binary else 'application/json'}), timeout=30) as response:
        chunks = []
        received = 0
        while received <= limit:
            chunk = response.read(min(65536, limit + 1 - received))
            if not chunk:
                break
            chunks.append(chunk)
            received += len(chunk)
            if progress:
                progress(min(100, received * 100 // limit))
        data = b''.join(chunks)
    require(len(data) <= limit, 'Resposta GitHub excede o tamanho permitido.')
    return data


def supports_local_files():
    message = QtDBus.QDBusMessage.createMethodCall(SERVICE, ROOT, PROPERTIES, 'Get')
    message.setArguments([SERVICE, 'Roles'])
    message.setInteractiveAuthorizationAllowed(False)
    reply = QtDBus.QDBusConnection.systemBus().call(message, QtDBus.QDBus.CallMode.Block, 5000)
    require(reply.type() != QtDBus.QDBusMessage.MessageType.ErrorMessage and bool(reply.arguments()),
            'Não foi possível consultar o suporte do PackageKit a arquivos locais.')
    roles = reply.arguments()[0]
    if hasattr(roles, 'variant'):
        roles = roles.variant()
    require(int(roles) & (1 << 10), 'O backend PackageKit desta VM não oferece InstallFiles. Nenhum fallback inseguro será utilizado.')


class GitHubTrial:
    def __init__(self, directory):
        self.directory = directory
        self.path = directory / 'pacotes' / (NAME + '_1.0_all.deb')
        self.release = None

    def verify_file(self):
        require(self.path.is_file() and not self.path.is_symlink(), 'Pacote experimental ausente ou simbólico.')
        require(self.path.stat().st_size == SIZE and hashlib.sha256(self.path.read_bytes()).hexdigest() == SHA256,
                'Integridade do Gestão de Drivers 1.0 divergente. A instalação foi bloqueada.')

    def load(self):
        # Lê ambos os arquivos no MESMO commit da main, evitando edição parcial.
        commit = decode(download('https://api.github.com/repos/mainuan/atualizadorderecursos/commits/main'))
        sha = commit.get('sha', '')
        require(bool(re.fullmatch(r'[a-f0-9]{40}', sha)), 'Referência GitHub inválida.')
        root = f'https://raw.githubusercontent.com/mainuan/atualizadorderecursos/{sha}/'
        names = download(root + 'packages.txt', 8192).decode('utf-8')
        message = download(root + 'message.txt', 16000).decode('utf-8').strip()
        repositories = [line.split('#', 1)[0].strip() for line in names.splitlines() if line.split('#', 1)[0].strip()]
        require(repositories == [REPOSITORY], 'Neste primeiro ensaio, packages.txt deve conter somente mainuan-gestao-drivers.')
        require(bool(message) and len(message) <= 4000 and '\x00' not in message, 'Mensagem vazia ou muito extensa.')
        repo = decode(download(f'https://api.github.com/repos/mainuan/{REPOSITORY}'))
        require(repo.get('id') == 1405529794 and repo.get('full_name') == 'mainuan/' + REPOSITORY
                and repo.get('owner', {}).get('login') == 'mainuan' and not repo.get('archived'), 'Repositório do programa divergente.')
        release = decode(download(f'https://api.github.com/repos/mainuan/{REPOSITORY}/releases/{RELEASE_ID}'))
        require(release.get('id') == RELEASE_ID and release.get('tag_name') == 'v1.0'
                and release.get('published_at') and not release.get('draft') and not release.get('prerelease'),
                'A release aprovada não está disponível como publicação estável.')
        assets = [asset for asset in release.get('assets', []) if asset.get('id') == ASSET_ID]
        require(len(assets) == 1, 'Artefato aprovado não encontrado.')
        asset = assets[0]
        require(asset.get('name') == self.path.name and asset.get('size') == SIZE
                and asset.get('digest') == 'sha256:' + SHA256 and asset.get('browser_download_url') == ASSET_URL,
                'A release foi alterada ou não corresponde ao pacote aprovado para este ensaio.')
        # O SHA aprovado vincula também o payload e os scripts de manutenção
        # já examinados: nenhum módulo, firmware, serviço ou autostart.
        published = datetime.fromisoformat(commit['commit']['committer']['date'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        require(published <= now + timedelta(minutes=5), 'Commit GitHub está no futuro. Confira o relógio da VM.')
        package = Package(NAME, VERSION, 'all', SHA256)
        self.release = Release('homologacao-github', sha[:12], 'O Mainuan tem novidades!', message,
                               RELEASE_URL, (Feature('Gestão de Drivers 1.0', (package,)),),
                               {'distro_id': ['ubuntu', 'mainuan'], 'version_id': ['2026', '26.04'],
                                'architecture': ['amd64', 'arm64']})
        content = (sha + '\n' + names + '\n' + message + '\n' + SHA256).encode()
        return Catalog(int(published.timestamp()), now + timedelta(hours=4), (self.release,), hashlib.sha256(content).hexdigest()), True

    def plan(self, release, check_dependencies=False):
        import apt
        import apt.debfile
        require(release == self.release, 'Lançamento experimental não aprovado.')
        cache = apt.Cache()
        pkg = cache[NAME] if NAME in cache else None
        installed = pkg.installed.version if pkg and pkg.installed else ''
        status = 'Atualizar' if installed else 'Instalar'
        if pkg and pkg.installed:
            if not configured(pkg):
                status = 'Pacote com configuração incompleta'
            elif version_compare(installed, VERSION) >= 0:
                status = 'Já recebido'
        if status in ('Instalar', 'Atualizar'):
            if pkg and pkg._pkg.selected_state == 2:
                status = 'Pacote retido pelo administrador'
            elif check_dependencies:
                self.verify_file()
                deb = apt.debfile.DebPackage(str(self.path), cache)
                require((deb['Package'], deb['Version'], deb['Architecture']) == (NAME, VERSION, 'all'), 'Metadados Debian divergentes.')
                if not deb.check():
                    status = 'Dependências não satisfeitas: ' + deb._failure_string
                elif any(deb.required_changes):
                    status = 'Este ensaio não permite alterar dependências: ' + ', '.join(name for group in deb.required_changes for name in group)
        return Plan((PackageRow(NAME, VERSION, installed, VERSION, 'all', status, SHA256),))

    def prepare_plan(self, release, progress):
        # A consulta inicial usa apenas metadados e o inventário instalado.
        # O arquivo e suas dependências só são examinados após a ação de instalar.
        plan = self.plan(release)
        if plan.complete or plan.blockers:
            return plan
        supports_local_files()
        if self.path.exists() or self.path.is_symlink():
            self.verify_file()
        else:
            progress('Baixando novidades...', 0)
            payload = download(ASSET_URL, SIZE, binary=True,
                               progress=lambda percent: progress('Baixando novidades...', percent))
            require(len(payload) == SIZE and hashlib.sha256(payload).hexdigest() == SHA256, 'Download do pacote com integridade inválida.')
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(payload)
            except BaseException:
                self.path.unlink(missing_ok=True)
                raise
        progress('Preparando instalação...', None)
        return self.plan(release, check_dependencies=True)


class GitHubController(Controller):
    def __init__(self, trial, parent=None, guard=lambda: None):
        self.trial = trial
        super().__init__(parent, plan_provider=self._prepare_plan, guard=guard,
                         transaction_factory=partial(Transaction, allow_local_files=True))

    def _prepare_plan(self, release):
        return self.trial.prepare_plan(release, self.progress.emit)

    def verification_plan(self, release):
        return self.trial.plan(release)

    def _planned(self, plan):
        if plan.blockers:
            return self._fail('Não é possível instalar neste ensaio:\n' + '\n'.join(row.status for row in plan.blockers), plan)
        if plan.complete:
            return self._finish(True, 'Você já recebeu o Gestão de Drivers 1.0. Nenhuma reinstalação será feita.', plan)
        if self.confirmed and plan != self.confirmed.plan:
            return self._fail('O estado de pacotes mudou. Revise a operação novamente.', plan)
        self.plan = plan
        self.ids = (str(self.trial.path),)
        self._work(supports_local_files, lambda _: self._tx('InstallFiles', self.ids, True, self._simulated))

    def _simulated(self, result):
        if not result.success:
            return self._fail(result.error)
        def validate():
            self.trial.verify_file()
            effects = tuple(sorted(result.packages))
            expected_info = 11 if self.plan.rows[0].installed else 12
            if len(effects) != 1 or effects[0][0] != expected_info or identity(effects[0][1]) != (NAME, VERSION, 'all'):
                raise PlanningError('O PackageKit propôs alterações além do aplicativo Gestão de Drivers. Nenhum driver ou dependência adicional será instalado neste ensaio.')
            return ((effects[0][0], effects[0][1], self.plan.rows[0].installed),)
        self._work(validate, self._validated)

    def _validated(self, evidence):
        if not self.confirmed:
            return super()._validated(evidence)
        if evidence != self.confirmed.evidence or self.ids != self.confirmed.ids:
            return self._fail('A operação mudou. Revise novamente a confirmação.')
        try:
            self.guard()
            self.trial.verify_file()
        except Exception as exc:
            return self._fail(str(exc))
        self.progress.emit('Instalando novidades...', None)
        self._tx('InstallFiles', self.ids, False, self._installed)
