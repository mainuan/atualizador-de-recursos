"""Canal oficial GitHub: metadados leves e instalação local validada por PackageKit.

HTTPS e o digest publicado pelo GitHub não são uma assinatura de repositório APT.
Nenhum arquivo Debian é baixado durante a consulta de novidades.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from . import __version__
from .catalog import (Catalog, CatalogError, Feature, Package, Release, NAME, VERSION,
                      decode, require, scoped_url, text, timestamp)
from .controller import Controller
from .github_trial import supports_local_files
from .i18n import _, message_languages
from .packagekit import Transaction
from .packages import INSTALL, RECEIVED, UPGRADE, PackageRow, Plan, configured, identity, version_compare
from .session import SessionKind, session_kind, system_identity, supported_system, system_compatibility
from .state import atomic_write

API = 'https://api.github.com/repos/mainuan/'
OFFICIAL = 'atualizador-de-recursos'
REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')
DEB = re.compile(r'([a-z0-9][a-z0-9+.-]+)_([^_/]+)_([a-z0-9][a-z0-9-]*)\.deb\Z')
MAX_PACKAGE = 128 * 1024 * 1024
MAX_CACHE = 8 * 1024 * 1024


def validate_url(url, repository=None, redirect=False):
    require(isinstance(url, str) and len(url) <= 4096 and not any(c.isspace() for c in url)
            and '\\' not in url, _('Invalid GitHub address.'))
    try:
        parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.port in (None, 443)
                and not parsed.username and not parsed.password and not parsed.fragment,
                _('GitHub address must use official HTTPS.'))
    except ValueError as exc:
        raise CatalogError(_('Invalid GitHub address.')) from exc
    path = unquote(parsed.path)
    require('%' not in path and '\\' not in path and '//' not in path
            and not any(p in ('.', '..') for p in path.split('/')), _('Ambiguous GitHub path.'))
    if repository:
        require(bool(REPO.fullmatch(repository)), _('Invalid repository.'))
        allowed = (parsed.hostname == 'github.com'
                   and path.startswith(f'/mainuan/{repository}/releases/download/') and not parsed.query)
        if redirect:
            allowed = allowed or parsed.hostname in ('release-assets.githubusercontent.com', 'objects.githubusercontent.com')
    else:
        allowed = ((parsed.hostname == 'api.github.com' and bool(re.match(
            r'^/repos/mainuan/[A-Za-z0-9][A-Za-z0-9._-]{0,99}(?:/|$)', path)))
            or (parsed.hostname == 'raw.githubusercontent.com'
                and bool(re.fullmatch(rf'/mainuan/{OFFICIAL}/[a-f0-9]{{40}}/(?:packages|message(?:\.[a-z]{{2,3}}(?:_[A-Z]{{2}})?)?)\.txt', path))))
    require(allowed, _('Source or redirect outside the official Mainuan organization.'))


class Redirects(HTTPRedirectHandler):
    def __init__(self, repository):
        super().__init__()
        self.repository = repository

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(self.repository is not None, _('The GitHub query was redirected; check the official source.'))
        validate_url(newurl, self.repository, redirect=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url, repository=None):
    validate_url(url, repository)
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), Redirects(repository))
    return opener.open(Request(url, headers={'User-Agent': f'Mainuan-Recursos/{__version__}',
        'Accept': 'application/octet-stream' if repository else 'application/vnd.github+json'}), timeout=30)


def metadata(url, limit=1024 * 1024):
    with open_url(url) as response:
        raw = response.read(limit + 1)
    require(len(raw) <= limit, _('GitHub metadata exceeds the allowed limit.'))
    return raw


def api(path):
    return decode(metadata(API + path))


def asset_metadata(repository, asset):
    require(isinstance(asset, dict), _('Invalid GitHub artifact.'))
    match = DEB.fullmatch(asset.get('name', ''))
    require(bool(match), _('Use the Debian name package_version_architecture.deb in the release.'))
    name, version, architecture = match.groups()
    require(bool(NAME.fullmatch(name)) and len(name) <= 100 and bool(VERSION.fullmatch(version))
            and not version.endswith('-') and len(version) <= 128, _('Invalid Debian name or version.'))
    digest = asset.get('digest', '')
    require(isinstance(digest, str) and bool(re.fullmatch(r'sha256:[a-f0-9]{64}', digest)),
            _('The release has no verifiable SHA-256 published by GitHub for {file}.').format(file=asset['name']))
    require(type(asset.get('id')) is int and asset['id'] > 0 and type(asset.get('size')) is int
            and 0 < asset['size'] <= MAX_PACKAGE and asset.get('state') == 'uploaded', _('Artifact unavailable or invalid size.'))
    validate_url(asset.get('browser_download_url'), repository)
    return {'repository': repository, 'asset_id': asset['id'], 'filename': asset['name'],
            'name': name, 'version': version, 'architecture': architecture, 'sha256': digest[7:],
            'size': asset['size'], 'url': asset['browser_download_url']}


def localized_message(root, base):
    """message.txt is written in Brazilian Portuguese.  Other sessions read
    message.<language>.txt (``message.ja.txt``, ``message.zh_TW.txt``) in the
    session's order of languages, then message.en.txt; a missing translation
    is never an error."""
    def fetch(language):
        try:
            message = metadata(root + f'message.{language}.txt', 16000).decode('utf-8').replace('\r\n', '\n')
        except HTTPError as exc:
            if exc.code == 404:
                exc.close()
                return None
            raise
        if not message.strip():
            return None
        text(message, 4000, multiline=True)
        return message

    for language in message_languages():
        if language.startswith('pt'):
            return base
        message = fetch(language)
        if message:
            return message
    if 'en' not in message_languages():
        message = fetch('en')
        if message:
            return message
    return base


class GitHubChannel:
    def __init__(self, directory, state):
        self.directory = Path(directory)
        self.state = state
        self.cache_path = self.directory / 'github-channel.json'
        self.cache = {'schema': 1, 'sequence': 0, 'digest': '', 'editions': [], 'pins': {}, 'repositories': {}}
        self.catalog = None
        self.online = False
        self.system = None
        self.paths = ()
        if self.cache_path.exists():
            with self.cache_path.open('rb') as stream:
                raw = stream.read(MAX_CACHE + 1)
            require(len(raw) <= MAX_CACHE, _('GitHub history exceeds the allowed limit.'))
            self.cache = decode_cache(raw)

    def _catalog(self, cache, expires):
        releases = []
        for edition in cache['editions']:
            r = edition['release']
            features = tuple(Feature(f['title'], tuple(Package(**p) for p in f['packages'])) for f in r['features'])
            # Cache 0.2.2: atualizar somente os filtros de plataforma do canal,
            # preservando bytes aprovados, edição, histórico e arquitetura.
            compatibility = {**r['compatibility'], **system_compatibility()}
            # The edition title is generated by the application (not editorial
            # content): show it in the current language, whatever the cache holds.
            releases.append(Release(**{**r, 'title': _('Mainuan has news!'), 'features': features,
                                       'compatibility': compatibility}))
        return Catalog(cache['sequence'], expires, tuple(releases), cache['digest'])

    def _select(self, name, architecture):
        repo = api(name)
        require(repo.get('full_name') == 'mainuan/' + name and repo.get('owner', {}).get('login') == 'mainuan'
                and type(repo.get('id')) is int and not repo.get('archived') and not repo.get('disabled'),
                _('Repository does not belong to the official organization or is unavailable: {repository}').format(repository=name))
        previous_id = self.cache['repositories'].get(name)
        require(previous_id in (None, repo['id']), _('The repository identity was replaced: {repository}').format(repository=name))
        # A API ordena por criação, não necessariamente por data de publicação.
        # Percorre a coleção completa limitada; nunca publica um resultado truncado.
        releases = []
        for page in range(1, 11):
            chunk = api(f'{name}/releases?per_page=100&page={page}')
            require(isinstance(chunk, list), _('Invalid list of releases: {repository}').format(repository=name))
            releases.extend(r for r in chunk if not r.get('draft') and not r.get('prerelease') and r.get('published_at'))
            if len(chunk) < 100:
                break
        else:
            raise CatalogError(_('Too many releases for a safe query: {repository}').format(repository=name))
        for release in sorted(releases, key=lambda r: timestamp(r['published_at']), reverse=True):
            require(timestamp(release['published_at']) <= datetime.now(timezone.utc) + timedelta(minutes=5),
                    _('Release with a future date. Check the system clock.'))
            require(type(release.get('id')) is int and release['id'] > 0, _('Invalid release ID.'))
            assets = []
            for page in range(1, 11):
                chunk = api(f"{name}/releases/{release['id']}/assets?per_page=100&page={page}")
                require(isinstance(chunk, list), _('Invalid list of artifacts.'))
                assets.extend(chunk)
                if len(chunk) < 100:
                    break
            else:
                raise CatalogError(_('Too many artifacts in the release.'))
            selected = []
            for asset in assets:
                match = DEB.fullmatch(asset.get('name', ''))
                if match and match[3] in ('all', architecture):
                    selected.append(asset_metadata(name, asset))
            if not selected:
                continue
            selected.sort(key=lambda a: (a['name'], a['architecture']))
            require(len(selected) <= 50 and len({a['name'] for a in selected}) == len(selected),
                    _('Duplicate or ambiguous packages in the release: {repository}').format(repository=name))
            article = scoped_url(release.get('html_url'), (f'https://github.com/mainuan/{name}/releases/',))
            for asset in selected:
                require(unquote(urlsplit(asset['url']).path) ==
                        f"/mainuan/{name}/releases/download/{release['tag_name']}/{asset['filename']}",
                        _('Artifact URL does not match the selected release.'))
            commit = api(name + '/commits/' + quote(release['tag_name'], safe='')).get('sha', '')
            require(bool(re.fullmatch('[a-f0-9]{40}', commit)), _('Invalid immutable reference of the release.'))
            for asset in selected:
                asset.update(repository_id=repo['id'], release_id=release['id'], commit=commit,
                             tag=release['tag_name'], article=article)
            friendly = text(release.get('name') or name, 150)
            return selected, Feature(friendly, tuple(Package(a['name'], a['version'], a['architecture'], a['sha256']) for a in selected))
        raise CatalogError(_('No stable release with a compatible Debian package: {repository}').format(repository=name))

    def load(self):
        self.online = False
        try:
            catalog, cache = self._load_online()
        except (OSError, URLError):
            if not self.cache['editions']:
                raise
            catalog = self._catalog(self.cache, datetime.now(timezone.utc))
            self.state.accept(catalog)
            self.catalog = catalog
            return catalog, False
        # A marca de sequência precede o cache; falha de persistência bloqueia instalação.
        self.state.accept(catalog)
        atomic_write(self.cache_path, json.dumps(cache, ensure_ascii=False).encode())
        self.cache, self.catalog, self.online = cache, catalog, True
        return catalog, True

    def _load_online(self):
        self.system = system_identity()
        require(supported_system(self.system),
                _('This channel is intended for Mainuan based on Kubuntu 26.04.'))
        commit = api(OFFICIAL + '/commits/main').get('sha', '')
        require(bool(re.fullmatch('[a-f0-9]{40}', commit)), _('Invalid official reference.'))
        root = f'https://raw.githubusercontent.com/mainuan/{OFFICIAL}/{commit}/'
        names = metadata(root + 'packages.txt', 8192).decode('utf-8')
        base = metadata(root + 'message.txt', 16000).decode('utf-8').replace('\r\n', '\n')
        require(bool(base.strip()), _('message.txt is empty.'))
        text(base, 4000, multiline=True)
        message = localized_message(root, base)
        repositories = [line.split('#', 1)[0].strip() for line in names.splitlines() if line.split('#', 1)[0].strip()]
        require(len(repositories) <= 20 and len(set(repositories)) == len(repositories)
                and all(REPO.fullmatch(n) and n not in ('.', '..') for n in repositories), _('packages.txt contains invalid or repeated repositories.'))
        features, assets = [], []
        for name in repositories:
            selected, feature = self._select(name, self.system['architecture'])
            features.append(feature)
            assets.extend(selected)
        require(len({a['name'] for a in assets}) == len(assets), _('Two repositories offer the same Debian package.'))
        pins, repo_ids = dict(self.cache['pins']), dict(self.cache['repositories'])
        for asset in assets:
            key = '/'.join(asset[k] for k in ('repository', 'name', 'version', 'architecture'))
            binding = {k: asset[k] for k in ('repository_id', 'release_id', 'asset_id', 'sha256', 'commit', 'size')}
            require(key not in pins or pins[key] == binding, _('An already announced release or artifact was replaced: {package}').format(package=asset['name']))
            for old in pins:
                repo, name, version, arch = old.split('/')
                if (repo, name, arch) == (asset['repository'], asset['name'], asset['architecture']):
                    require(version_compare(asset['version'], version) >= 0, _('Rollback of a published version blocked: {package}').format(package=name))
            pins[key] = binding
            repo_ids[asset['repository']] = asset['repository_id']
        content = json.dumps({'message': base, 'repositories': repositories, 'assets': assets,
                              'features': [asdict(f) for f in features]}, sort_keys=True, ensure_ascii=False).encode()
        digest = hashlib.sha256(content).hexdigest()
        sequence = self.state.data['sequence']
        if digest != self.state.data['digest']:
            sequence += 1
        sequence = max(1, sequence)
        edition = Release('github', digest[:24], _('Mainuan has news!'), message,
                          assets[0]['article'] if assets else f'https://github.com/mainuan/{OFFICIAL}/releases',
                          tuple(features), system_compatibility((self.system['architecture'],)))
        previous = [e for e in self.cache['editions'] if e['release']['version'] != edition.version]
        editions = ([{'release': asdict(edition), 'assets': assets}] if features else []) + previous
        cache = {'schema': 1, 'sequence': sequence, 'digest': digest, 'editions': editions[:50],
                 'pins': pins, 'repositories': repo_ids}
        require(len(json.dumps(cache).encode()) <= MAX_CACHE, _('GitHub history exceeds the allowed limit.'))
        return self._catalog(cache, datetime.now(timezone.utc) + timedelta(hours=4)), cache

    def _assets(self, release):
        require(self.catalog is not None and release in self.catalog.releases, _('News not queried in this channel.'))
        return next(e['assets'] for e in self.cache['editions'] if e['release']['version'] == release.version)

    def path(self, asset):
        return self.directory / 'pacotes-github' / asset['sha256'] / asset['filename']

    def verify_file(self, asset):
        path = self.path(asset)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == asset['size'], _('Package missing or size mismatch.'))
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == asset['sha256'], _('SHA-256 integrity mismatch; installation blocked.'))
        import apt.debfile
        deb = apt.debfile.DebPackage(str(path))
        require(tuple(deb[k] for k in ('Package', 'Version', 'Architecture')) ==
                tuple(asset[k] for k in ('name', 'version', 'architecture')), _('Internal package metadata does not match the release.'))

    def plan(self, release, check_dependencies=False):
        import apt
        import apt.debfile
        cache = apt.Cache()
        rows = []
        for asset in self._assets(release):
            name, version, arch = (asset[k] for k in ('name', 'version', 'architecture'))
            key = f'{name}:{arch}' if f'{name}:{arch}' in cache else name
            pkg = cache[key] if key in cache else None
            installed = pkg.installed.version if pkg and pkg.installed else ''
            status = UPGRADE if installed else INSTALL
            if installed and not configured(pkg):
                status = _('Package with incomplete configuration')
            elif installed and version_compare(installed, version) >= 0:
                status = RECEIVED
            elif pkg and pkg._pkg.selected_state == 2:
                status = _('Package held by the administrator')
            elif check_dependencies:
                self.verify_file(asset)
                deb = apt.debfile.DebPackage(str(self.path(asset)), cache)
                if not deb.check():
                    # deb._failure_string is raw APT output and stays untranslated.
                    status = _('Unmet dependencies: {details}').format(details=deb._failure_string)
                elif any(deb.required_changes):
                    status = _('The operation requires additional unannounced packages')
            rows.append(PackageRow(name, version, installed, version, arch, status, asset['sha256']))
        return Plan(tuple(rows))

    def _refresh_asset(self, asset):
        release = api(f"{asset['repository']}/releases/{asset['release_id']}")
        require(release.get('id') == asset['release_id'] and release.get('published_at')
                and not release.get('draft') and not release.get('prerelease')
                and release.get('tag_name') == asset['tag'], _('The announced release was withdrawn or changed.'))
        commit = api(asset['repository'] + '/commits/' + quote(asset['tag'], safe='')).get('sha')
        require(commit == asset['commit'], _('The release reference was replaced; installation blocked.'))
        remote = api(f"{asset['repository']}/releases/assets/{asset['asset_id']}")
        current = asset_metadata(asset['repository'], remote)
        require(all(current[k] == asset[k] for k in current), _('The artifact was changed after the query; check for news again.'))

    def _download(self, asset, progress):
        path = self.path(asset)
        if path.exists() or path.is_symlink():
            self.verify_file(asset)
            return
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.download-')
        try:
            received, digest = 0, hashlib.sha256()
            with os.fdopen(descriptor, 'wb') as stream, open_url(asset['url'], asset['repository']) as response:
                while True:
                    chunk = response.read(min(65536, asset['size'] + 1 - received))
                    if not chunk:
                        break
                    received += len(chunk)
                    require(received <= asset['size'], _('Download exceeds the approved size.'))
                    digest.update(chunk)
                    stream.write(chunk)
                    progress(_('Downloading new features...'), received * 100 // asset['size'])
            require(received == asset['size'] and digest.hexdigest() == asset['sha256'], _('Download with SHA-256 integrity mismatch.'))
            os.replace(temporary, path)
            self.verify_file(asset)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def prepare_plan(self, release, progress):
        require(self.online, _('Check for news online before installing.'))
        require(os.geteuid() != 0 and session_kind() == SessionKind.INSTALLED,
                _('Installation requires a regular user and an installed session, outside Live mode.'))
        plan = self.plan(release)
        if plan.complete or plan.blockers:
            return plan
        supports_local_files()
        pending = {r.name for r in plan.pending}
        assets = [a for a in self._assets(release) if a['name'] in pending]
        for asset in assets:
            self._refresh_asset(asset)
            progress(_('Downloading new features...'), 0)
            self._download(asset, progress)
        self.paths = tuple(str(self.path(a)) for a in assets)
        progress(_('Preparing installation...'), None)
        return self.plan(release, check_dependencies=True)

    def validate_simulation(self, release, plan, effects):
        for asset in self._assets(release):
            if asset['name'] in {r.name for r in plan.pending}:
                self.verify_file(asset)
        pending = {r.identity: r for r in plan.pending}
        require(len(effects) == len(pending), _('PackageKit proposed additional packages or an incomplete operation.'))
        evidence, seen = [], set()
        for info, package_id in effects:
            key = identity(package_id)
            require(key in pending and key not in seen, _('The simulation would change unannounced packages.'))
            row = pending[key]
            require(info == (11 if row.installed else 12), _('Removal, reinstallation or downgrade blocked.'))
            seen.add(key)
            evidence.append((info, package_id, row.installed))
        return tuple(sorted(evidence))


def decode_cache(raw):
    try:
        # O cache é local, não um catálogo remoto autenticado nem uma assinatura APT.
        obj = json.loads(raw)
        require(obj['schema'] == 1 and type(obj['sequence']) is int and obj['sequence'] > 0
                and bool(re.fullmatch('[a-f0-9]{64}', obj['digest'])) and len(obj['editions']) <= 50,
                _('Invalid GitHub cache.'))
        require(isinstance(obj['pins'], dict) and isinstance(obj['repositories'], dict), _('Invalid GitHub cache.'))
        for edition in obj['editions']:
            r = edition['release']
            text(r['summary'], 4000, multiline=True)
            scoped_url(r['article_url'], ('https://github.com/mainuan/',))
            require(r['id'] == 'github' and bool(re.fullmatch('[a-f0-9]{24}', r['version'])), _('Invalid local edition.'))
            for asset in edition['assets']:
                require(bool(REPO.fullmatch(asset['repository'])) and bool(DEB.fullmatch(asset['filename']))
                        and bool(re.fullmatch('[a-f0-9]{64}', asset['sha256'])), _('Invalid local artifact.'))
                validate_url(asset['url'], asset['repository'])
        return obj
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise CatalogError(_('Invalid GitHub history. Preserve the file before recovering it.')) from exc


class GitHubController(Controller):
    def __init__(self, channel, parent=None, guard=lambda: None):
        self.channel = channel
        super().__init__(parent, plan_provider=self._prepare_plan, guard=guard,
                         transaction_factory=partial(Transaction, allow_local_files=True))

    def _prepare_plan(self, release):
        return self.channel.prepare_plan(release, self.progress.emit)

    def verification_plan(self, release):
        return self.channel.plan(release)

    def _planned(self, plan):
        if plan.blockers:
            return self._fail(_('Cannot install:') + '\n' + '\n'.join(f'{r.name}: {r.status}' for r in plan.blockers), plan)
        if plan.complete:
            return self._finish(True, _('You have already received all the features. No reinstallation will be done.'), plan)
        if self.confirmed and plan != self.confirmed.plan:
            return self._fail(_('The package state has changed. Check for news again.'), plan)
        self.plan, self.ids = plan, self.channel.paths
        self._tx('InstallFiles', self.ids, True, self._simulated)

    def _simulated(self, result):
        if not result.success:
            return self._fail(result.error)
        self._work(lambda: self.channel.validate_simulation(self.release, self.plan, result.packages), self._validated)

    def _validated(self, evidence):
        if not self.confirmed:
            return super()._validated(evidence)
        if evidence != self.confirmed.evidence or self.ids != self.confirmed.ids:
            return self._fail(_('The operation has changed; installation blocked.'))
        try:
            self.guard()
            for asset in self.channel._assets(self.release):
                if str(self.channel.path(asset)) in self.ids:
                    self.channel.verify_file(asset)
        except Exception as exc:
            return self._fail(str(exc))
        self.progress.emit(_('Installing new features...'), None)
        self._tx('InstallFiles', self.ids, False, self._installed)
