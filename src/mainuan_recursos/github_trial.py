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
from .i18n import _
from .packagekit import Transaction, ROOT, SERVICE, PROPERTIES
from .packages import INSTALL, RECEIVED, UPGRADE, PackageRow, Plan, PlanningError, configured, identity, version_compare
from .session import SessionKind, session_kind, system_identity, supported_system, system_compatibility

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
    require(result.returncode == 0, _('The GitHub acceptance test is exclusive to a VM with a snapshot; use the normal mode on this computer.'))
    require(os.geteuid() != 0, _('Open the acceptance test as a regular user, without sudo.'))
    require(session_kind() == SessionKind.INSTALLED, _('The acceptance test requires a normal installation, outside the Live session.'))
    system = system_identity()
    require(supported_system(system), _('This trial is intended for Mainuan based on Kubuntu 26.04.'))


def check_url(url, binary=False):
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username
            and not parsed.password and not parsed.fragment, _('Invalid acceptance test URL.'))
    allowed = ((parsed.hostname == 'api.github.com' and parsed.path.startswith('/repos/mainuan/'))
               or (parsed.hostname == 'raw.githubusercontent.com'
                   and parsed.path.startswith('/mainuan/atualizadorderecursos/')))
    if binary:
        allowed = allowed or (parsed.hostname == 'github.com' and parsed.path.startswith('/mainuan/mainuan-gestao-drivers/releases/download/'))
        allowed = allowed or parsed.hostname in ('release-assets.githubusercontent.com', 'objects.githubusercontent.com')
    require(allowed, _('Redirect outside the authorized GitHub infrastructure.'))


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
    require(len(data) <= limit, _('GitHub response exceeds the allowed size.'))
    return data


def supports_local_files():
    message = QtDBus.QDBusMessage.createMethodCall(SERVICE, ROOT, PROPERTIES, 'Get')
    message.setArguments([SERVICE, 'Roles'])
    message.setInteractiveAuthorizationAllowed(False)
    reply = QtDBus.QDBusConnection.systemBus().call(message, QtDBus.QDBus.CallMode.Block, 5000)
    require(reply.type() != QtDBus.QDBusMessage.MessageType.ErrorMessage and bool(reply.arguments()),
            _('Could not query PackageKit support for local files.'))
    roles = reply.arguments()[0]
    if hasattr(roles, 'variant'):
        roles = roles.variant()
    require(int(roles) & (1 << 10), _('The PackageKit backend of this VM does not offer InstallFiles. No unsafe fallback will be used.'))


class GitHubTrial:
    def __init__(self, directory):
        self.directory = directory
        self.path = directory / 'pacotes' / (NAME + '_1.0_all.deb')
        self.release = None

    def verify_file(self):
        require(self.path.is_file() and not self.path.is_symlink(), _('Experimental package missing or symbolic.'))
        require(self.path.stat().st_size == SIZE and hashlib.sha256(self.path.read_bytes()).hexdigest() == SHA256,
                _('Driver Manager 1.0 integrity mismatch. The installation was blocked.'))

    def load(self):
        # Lê ambos os arquivos no MESMO commit da main, evitando edição parcial.
        commit = decode(download('https://api.github.com/repos/mainuan/atualizadorderecursos/commits/main'))
        sha = commit.get('sha', '')
        require(bool(re.fullmatch(r'[a-f0-9]{40}', sha)), _('Invalid GitHub reference.'))
        root = f'https://raw.githubusercontent.com/mainuan/atualizadorderecursos/{sha}/'
        names = download(root + 'packages.txt', 8192).decode('utf-8')
        message = download(root + 'message.txt', 16000).decode('utf-8').strip()
        repositories = [line.split('#', 1)[0].strip() for line in names.splitlines() if line.split('#', 1)[0].strip()]
        require(repositories == [REPOSITORY], _('In this first trial, packages.txt must contain only mainuan-gestao-drivers.'))
        require(bool(message) and len(message) <= 4000 and '\x00' not in message, _('Message empty or too long.'))
        repo = decode(download(f'https://api.github.com/repos/mainuan/{REPOSITORY}'))
        require(repo.get('id') == 1405529794 and repo.get('full_name') == 'mainuan/' + REPOSITORY
                and repo.get('owner', {}).get('login') == 'mainuan' and not repo.get('archived'), _('Program repository mismatch.'))
        release = decode(download(f'https://api.github.com/repos/mainuan/{REPOSITORY}/releases/{RELEASE_ID}'))
        require(release.get('id') == RELEASE_ID and release.get('tag_name') == 'v1.0'
                and release.get('published_at') and not release.get('draft') and not release.get('prerelease'),
                _('The approved release is not available as a stable publication.'))
        assets = [asset for asset in release.get('assets', []) if asset.get('id') == ASSET_ID]
        require(len(assets) == 1, _('Approved artifact not found.'))
        asset = assets[0]
        require(asset.get('name') == self.path.name and asset.get('size') == SIZE
                and asset.get('digest') == 'sha256:' + SHA256 and asset.get('browser_download_url') == ASSET_URL,
                _('The release was changed or does not match the package approved for this trial.'))
        # O SHA aprovado vincula também o payload e os scripts de manutenção
        # já examinados: nenhum módulo, firmware, serviço ou autostart.
        published = datetime.fromisoformat(commit['commit']['committer']['date'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        require(published <= now + timedelta(minutes=5), _('GitHub commit is in the future. Check the VM clock.'))
        package = Package(NAME, VERSION, 'all', SHA256)
        self.release = Release('homologacao-github', sha[:12], _('Mainuan has news!'), message,
                               RELEASE_URL, (Feature(_('Driver Manager 1.0'), (package,)),),
                               system_compatibility(('amd64', 'arm64')))
        content = (sha + '\n' + names + '\n' + message + '\n' + SHA256).encode()
        return Catalog(int(published.timestamp()), now + timedelta(hours=4), (self.release,), hashlib.sha256(content).hexdigest()), True

    def plan(self, release, check_dependencies=False):
        import apt
        import apt.debfile
        require(release == self.release, _('Experimental release not approved.'))
        cache = apt.Cache()
        pkg = cache[NAME] if NAME in cache else None
        installed = pkg.installed.version if pkg and pkg.installed else ''
        status = UPGRADE if installed else INSTALL
        if pkg and pkg.installed:
            if not configured(pkg):
                status = _('Package with incomplete configuration')
            elif version_compare(installed, VERSION) >= 0:
                status = RECEIVED
        if status in (INSTALL, UPGRADE):
            if pkg and pkg._pkg.selected_state == 2:
                status = _('Package held by the administrator')
            elif check_dependencies:
                self.verify_file()
                deb = apt.debfile.DebPackage(str(self.path), cache)
                require((deb['Package'], deb['Version'], deb['Architecture']) == (NAME, VERSION, 'all'), _('Debian metadata mismatch.'))
                if not deb.check():
                    status = _('Unmet dependencies: {details}').format(details=deb._failure_string)
                elif any(deb.required_changes):
                    status = _('This trial does not allow changing dependencies: {packages}').format(
                        packages=', '.join(name for group in deb.required_changes for name in group))
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
            progress(_('Downloading new features...'), 0)
            payload = download(ASSET_URL, SIZE, binary=True,
                               progress=lambda percent: progress(_('Downloading new features...'), percent))
            require(len(payload) == SIZE and hashlib.sha256(payload).hexdigest() == SHA256, _('Package download with invalid integrity.'))
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(payload)
            except BaseException:
                self.path.unlink(missing_ok=True)
                raise
        progress(_('Preparing installation...'), None)
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
            return self._fail(_('Cannot install in this trial:') + '\n' + '\n'.join(row.status for row in plan.blockers), plan)
        if plan.complete:
            return self._finish(True, _('You have already received Driver Manager 1.0. No reinstallation will be done.'), plan)
        if self.confirmed and plan != self.confirmed.plan:
            return self._fail(_('The package state has changed. Review the operation again.'), plan)
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
                raise PlanningError(_('PackageKit proposed changes beyond the Driver Manager application. No additional driver or dependency will be installed in this trial.'))
            return ((effects[0][0], effects[0][1], self.plan.rows[0].installed),)
        self._work(validate, self._validated)

    def _validated(self, evidence):
        if not self.confirmed:
            return super()._validated(evidence)
        if evidence != self.confirmed.evidence or self.ids != self.confirmed.ids:
            return self._fail(_('The operation has changed. Review the confirmation again.'))
        try:
            self.guard()
            self.trial.verify_file()
        except Exception as exc:
            return self._fail(str(exc))
        self.progress.emit(_('Installing new features...'), None)
        self._tx('InstallFiles', self.ids, False, self._installed)
