"""Publicador: entradas humanas simples, saída APT/catalogo autenticada e congelada.

Não instala pacotes e não executa código dos repositórios ou dos arquivos Debian.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from mainuan_recursos.catalog import (Config, NAME, VERSION, authenticate, parse_catalog,
                                     scoped_url, text, timestamp, unique_object)
from mainuan_recursos.packages import version_compare

MAX_ASSET = 25 * 1024 * 1024
MAX_POOL = 256 * 1024 * 1024
GREETING = 'Olá! O Mainuan tem novidades. Confira quais são:'
REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')


class PublicationError(ValueError):
    pass


def check(condition, message):
    if not condition:
        raise PublicationError(message)


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(raw):
    check(len(raw) <= 8 * 1024 * 1024, 'Metadados excedem o limite.')
    return json.loads(raw, object_pairs_hook=unique_object)


def inputs(packages, message):
    check(len(packages) <= 16384 and len(message) <= 8000, 'Entradas excedem o limite.')
    names = []
    for line in packages.decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        check(bool(REPO.fullmatch(line)) and line not in ('.', '..')
              and line.lower() not in {n.lower() for n in names},
              'packages.txt: use nomes únicos de repositórios Mainuan, um por linha; não use URLs.')
        names.append(line)
    check(0 < len(names) <= 50, 'packages.txt deve conter de 1 a 50 repositórios.')
    message = message.decode('utf-8').replace('\r\n', '\n').strip() or GREETING
    text(message, 2000, multiline=True)
    return names, message


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        check(parsed.scheme == 'https' and parsed.hostname in (
            'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com')
              and parsed.port in (None, 443) and not parsed.username and not parsed.password
              and not parsed.fragment and '\\' not in newurl, 'Redirecionamento de artefato não autorizado.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise PublicationError('A API redirecionou o repositório; revise seu nome/organização.')


class GitHub:
    def __init__(self, token=''):
        self.token = token

    def api(self, path):
        check(path.startswith('/repos/mainuan/'), 'Organização não autorizada.')
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                   'User-Agent': 'Mainuan-Publicador'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        try:
            with build_opener(HTTPSHandler(), NoRedirect()).open(
                    Request('https://api.github.com' + path, headers=headers), timeout=30) as response:
                return read_json(response.read(8 * 1024 * 1024 + 1))
        except HTTPError as exc:
            # Nunca imprimir headers, tokens, corpo remoto ou URLs de redirecionamento assinadas.
            raise PublicationError(f'GitHub: HTTP {exc.code} ao consultar {path.split("?")[0]}.') from None

    def pages(self, path):
        rows = []
        for page in range(1, 11):
            chunk = self.api(f'{path}?per_page=100&page={page}')
            check(isinstance(chunk, list), 'Lista GitHub inválida.')
            rows.extend(chunk)
            if len(chunk) < 100:
                return rows
        raise PublicationError('Mais de 1000 registros: limite de segurança atingido.')

    def repository(self, name):
        return self.api('/repos/mainuan/' + name)

    def releases(self, name):
        return self.pages('/repos/mainuan/' + name + '/releases')

    def commit(self, name, tag):
        return self.api('/repos/mainuan/' + name + '/commits/' + quote(tag, safe=''))['sha']

    def assets(self, name, release_id):
        return self.pages(f'/repos/mainuan/{name}/releases/{release_id}/assets')

    def download(self, name, asset):
        # Público, sem token: credenciais não atravessam os redirects para o CDN.
        url = asset['browser_download_url']
        scoped_url(url, (f'https://github.com/mainuan/{name}/releases/download/',))
        check(not urlsplit(url).query, 'URL de download inicial ambígua.')
        with build_opener(HTTPSHandler(), Redirects()).open(
                Request(url, headers={'User-Agent': 'Mainuan-Publicador'}), timeout=60) as response:
            raw = response.read(MAX_ASSET + 1)
        check(0 < len(raw) <= MAX_ASSET, 'Artefato excede 25 MiB ou está vazio.')
        return raw


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)


def inspect_deb(path):
    # dpkg-deb --field somente lê control; nunca extrai payload na raiz ou executa maintainer scripts.
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(['dpkg-deb', '--field', str(path)], stdout=output,
                                stderr=subprocess.DEVNULL, timeout=20, preexec_fn=limits)
        check(result.returncode == 0, 'Arquivo Debian inválido ou control excede os limites.')
        output.seek(0)
        raw = output.read(1024 * 1024 + 1)
    check(len(raw) <= 1024 * 1024, 'Control Debian excessivo.')
    import apt_pkg
    section = apt_pkg.TagSection(raw.decode('utf-8'))
    name, version, arch = (section.get(k, '') for k in ('Package', 'Version', 'Architecture'))
    check(bool(NAME.fullmatch(name)) and len(name) <= 100, 'Nome Debian inválido no control.')
    check(bool(VERSION.fullmatch(version)) and len(version) <= 128 and not version.endswith('-'),
          'Versão Debian inválida no control.')
    check(bool(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,30}', arch)), 'Arquitetura Debian inválida.')
    return {'name': name, 'version': version, 'architecture': arch}


def validate_policy(policy, production):
    check(policy['organization'] == 'mainuan' and len(policy['architectures']) == 1,
          'Política deve autorizar Mainuan e uma arquitetura de destino por canal.')
    check(bool(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,30}', policy['architectures'][0])), 'Arquitetura inválida.')
    scoped_url(policy['article_url'], ('https://github.com/mainuan/',)) if policy.get('article_url') else None
    if production:
        check(policy.get('enabled') is True, 'Produção desativada em publication.toml.')
    check(policy.get('catalog_public_key') and policy.get('catalog_key_id'), 'Chave pública do catálogo ausente.')
    check(bool(re.fullmatch(r'[0-9A-F]{40,64}', policy.get('apt_fingerprint', ''))),
          'Fingerprint completo da chave APT ausente.')


def signature(raw, key, key_id):
    return encoded({'key_id': key_id, 'signature': base64.b64encode(key.sign(raw)).decode()})


def verify(raw, envelope, public, key_id):
    obj = read_json(envelope)
    check(set(obj) == {'key_id', 'signature'} and obj['key_id'] == key_id, 'Assinatura de publicação inválida.')
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public, validate=True)).verify(
            base64.b64decode(obj['signature'], validate=True), raw)
    except Exception:
        raise PublicationError('Assinatura de publicação inválida.') from None


def load_previous(root, policy):
    ledger = root / 'catalogo/publicacao.json'
    sig = root / 'catalogo/publicacao.json.sig'
    check(ledger.exists() == sig.exists(), 'Estado anterior incompleto; publicação bloqueada.')
    if not ledger.exists():
        # Bootstrap explícito. Não iniciar novamente só porque alguém apagou o estado.
        check(policy.get('bootstrap') is True, 'Estado anterior ausente; habilite bootstrap apenas na primeira edição.')
        check(not (root / 'apt/InRelease').exists() and not (root / 'catalogo/novidades.json.sig').exists(),
              'Bootstrap recusado: há uma publicação anterior sem o registro autenticado.')
        return None
    raw = ledger.read_bytes()
    trusted_keys = dict(policy.get('previous_catalog_keys', {}))
    trusted_keys[policy['catalog_key_id']] = policy['catalog_public_key']
    def verify_previous(data, envelope):
        key_id = read_json(envelope).get('key_id')
        check(key_id in trusted_keys, 'Chave do registro anterior não está autorizada na política.')
        verify(data, envelope, trusted_keys[key_id], key_id)
    verify_previous(raw, sig.read_bytes())
    obj = read_json(raw)
    check(obj['schema_version'] == 1 and type(obj['sequence']) is int and obj['sequence'] > 0,
          'Estado de publicação inválido.')
    cat = (root / 'catalogo/novidades.json').read_bytes()
    verify_previous(cat, (root / 'catalogo/novidades.json.sig').read_bytes())
    check(obj['catalog_sha256'] == digest(cat), 'Catálogo e registro anterior divergem.')
    catalog = read_json(cat)
    check(catalog['sequence'] == obj['sequence'], 'Sequência anterior inconsistente.')
    # Uma edição expirada pode ser renovada, mas continua precisando de assinatura válida.
    parse_catalog(cat, ('github.com',), now=timestamp(catalog['published_at']),
                  article_prefixes=('https://github.com/mainuan/',))
    obj['catalog'] = catalog
    return obj


def select(name, github, cutoff, architecture, pool):
    repo = github.repository(name)
    check(repo.get('full_name', '').lower() == f'mainuan/{name}'.lower()
          and repo.get('owner', {}).get('login', '').lower() == 'mainuan'
          and repo.get('owner', {}).get('type') == 'Organization'
          and not repo.get('private', True) and not repo.get('archived', True)
          and not repo.get('disabled', False),
          f'{name}: repositório público oficial não encontrado ou não elegível.')
    releases = [r for r in github.releases(name) if not r.get('draft', True)
                and not r.get('prerelease', True) and r.get('published_at')
                and timestamp(r['published_at']) <= cutoff]
    check(releases, f'{name}: nenhuma release estável publicada/aprovada na data da autorização.')
    release = max(releases, key=lambda r: (timestamp(r['published_at']), r['id']))
    check(timestamp(release['updated_at']) <= cutoff, f'{name}: release mudou após a autorização; publique novamente packages.txt.')
    commit = github.commit(name, release['tag_name'])
    check(isinstance(commit, str) and bool(COMMIT.fullmatch(commit)), f'{name}: commit Git inválido.')
    title = (release.get('name') or repo.get('description') or name).strip()
    text(title, 150)
    source = {'repository': repo['full_name'], 'repository_id': repo['id'], 'release_id': release['id'],
              'commit': commit, 'assets': []}
    article = scoped_url(release['html_url'], (f'https://github.com/mainuan/{name}/releases/',))
    assets = [a for a in github.assets(name, release['id']) if a['name'].endswith('.deb')]
    check(assets, f'{name}: release sem pacote Debian .deb.')
    check(len(assets) <= 50, f'{name}: artefatos demais.')
    names = set()
    for asset in assets:
        expected = asset.get('digest', '')
        check(asset.get('state') == 'uploaded' and type(asset.get('id')) is int and asset['id'] > 0
              and type(asset.get('size')) is int and 0 < asset['size'] <= MAX_ASSET
              and expected.startswith('sha256:') and bool(SHA.fullmatch(expected[7:])),
              f'{name}: artefato indisponível, sem SHA-256 GitHub ou maior que 25 MiB.')
        check(timestamp(asset['updated_at']) <= cutoff and timestamp(asset['created_at']) <= cutoff,
              f'{name}: artefato adicionado/alterado após a autorização.')
        raw = github.download(name, asset)
        check(len(raw) == asset['size'] and digest(raw) == expected[7:], f'{name}: integridade/tamanho do artefato divergente.')
        path = pool / (digest(raw) + '.deb')
        path.write_bytes(raw)
        try:
            package = inspect_deb(path)
        except Exception:
            raise PublicationError(f'{name}: arquivo Debian inválido ou metadados excedem os limites.') from None
        if package['architecture'] not in ('all', architecture):
            path.unlink(missing_ok=True)
            continue
        check(package['name'] not in names, f'{name}: mais de um artefato elegível para o mesmo pacote.')
        names.add(package['name'])
        package.update(asset_id=asset['id'], sha256=expected[7:])
        source['assets'].append(package)
    check(source['assets'], f'{name}: não há pacote Debian para {architecture}/all.')
    source['assets'].sort(key=lambda a: a['name'])
    return {'title': title, 'article_url': article, 'source': source}


def verify_pool(root, previous, pool):
    if not previous:
        return
    for sha in previous['pool']:
        check(bool(SHA.fullmatch(sha)), 'Hash inválido no registro anterior.')
        path = root / 'apt/pool' / (sha + '.deb')
        check(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_ASSET,
              'Pacote histórico ausente ou excessivo.')
        check(digest(path.read_bytes()) == sha, 'Integridade do repositório APT histórico inválida.')
        shutil.copyfile(path, pool / path.name)


def create_apt(root, gpg_home, fingerprint, now, previous_root=None):
    apt = root / 'apt'
    result = subprocess.run(['dpkg-scanpackages', '--multiversion', 'pool', '/dev/null'], cwd=apt,
                            capture_output=True, check=True, timeout=60)
    packages = result.stdout
    (apt / 'Packages').write_bytes(packages)
    (apt / 'Packages.gz').write_bytes(gzip.compress(packages, mtime=0))
    # Preservar índices anteriores evita corrida entre InRelease e Packages no CDN.
    by_hash = apt / 'by-hash/SHA256'
    by_hash.mkdir(parents=True)
    if previous_root and (previous_root / 'apt/by-hash/SHA256').exists():
        for path in (previous_root / 'apt/by-hash/SHA256').iterdir():
            check(path.is_file() and not path.is_symlink() and bool(SHA.fullmatch(path.name))
                  and path.stat().st_size <= 8 * 1024 * 1024 and digest(path.read_bytes()) == path.name,
                  'Índice histórico por hash inválido.')
            shutil.copyfile(path, by_hash / path.name)
    release = ('Origin: Mainuan\nLabel: Recursos Mainuan\nSuite: recursos\nCodename: recursos\n'
               f'Date: {format_datetime(now, usegmt=True)}\n'
               f'Valid-Until: {format_datetime(now + timedelta(days=30), usegmt=True)}\n'
               'Acquire-By-Hash: yes\nDescription: Recursos aprovados pelo Mainuan\nSHA256:\n')
    for name in ('Packages', 'Packages.gz'):
        raw = (apt / name).read_bytes()
        (by_hash / digest(raw)).write_bytes(raw)
        release += f' {digest(raw)} {len(raw)} {name}\n'
    (apt / 'Release').write_text(release, encoding='utf-8')
    gpg = ['gpg', '--homedir', str(gpg_home), '--batch', '--yes', '--no-tty', '--local-user', fingerprint]
    for options in (['--clearsign', '--output', str(apt / 'InRelease')],
                    ['--detach-sign', '--output', str(apt / 'Release.gpg')]):
        result = subprocess.run(gpg + options + [str(apt / 'Release')], capture_output=True, timeout=60)
        check(result.returncode == 0, 'Falha na assinatura APT; nada será publicado.')
    # Verificar com keyring que contém apenas a chave pública selecionada.
    with tempfile.TemporaryDirectory() as temp:
        keyring = Path(temp) / 'apt.gpg'
        public = subprocess.run(gpg + ['--export', fingerprint], capture_output=True, check=True).stdout
        check(bool(public), 'Chave APT pública ausente.')
        keyring.write_bytes(public)
        for args in ([str(apt / 'InRelease')], [str(apt / 'Release.gpg'), str(apt / 'Release')]):
            result = subprocess.run(['gpgv', '--keyring', str(keyring)] + args, capture_output=True, timeout=30)
            check(result.returncode == 0, 'Verificação da assinatura APT falhou.')


def publish(packages, message, *, policy, github, previous_root, output, private_key,
            gpg_home, approval_commit, approval_time, now=None, production=True, refresh=False):
    """Gera árvore completa em diretório NOVO; só o workflow a publica após sucesso.

    Alterar bytes de packages.txt autoriza nova seleção. Mensagem isolada e
    renovação periódica reutilizam exatamente os IDs/bytes aprovados anteriormente.
    """
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    validate_policy(policy, production)
    check(bool(COMMIT.fullmatch(approval_commit)), 'Commit de autorização inválido.')
    check(approval_time <= now + timedelta(minutes=5), 'Autorização com data futura.')
    check(private_key is not None, 'Chave privada ausente; publicação de produção bloqueada.')
    try:
        key = serialization.load_pem_private_key(private_key, password=None)
        check(isinstance(key, Ed25519PrivateKey), 'Chave deve ser Ed25519.')
        verify(b'preflight', signature(b'preflight', key, policy['catalog_key_id']),
               policy['catalog_public_key'], policy['catalog_key_id'])
    except Exception:
        raise PublicationError('Chave privada ausente, inválida ou diferente da chave pública configurada.') from None
    names, summary = inputs(packages, message)
    previous = load_previous(previous_root, policy)
    check(not output.exists(), 'Diretório de saída já existe; não sobrescrever publicação.')
    refresh = refresh or not previous or digest(packages) != previous['packages_sha256']
    # Construir em staging: uma falha não deixa catálogo parcial na saída.
    with tempfile.TemporaryDirectory(prefix='mainuan-publicar-', dir=output.parent) as temp:
        stage = Path(temp)
        pool = stage / 'apt/pool'
        pool.mkdir(parents=True)
        verify_pool(previous_root, previous, pool)
        selected = ([select(n, github, approval_time, policy['architectures'][0], pool) for n in names]
                    if refresh else previous['selected'])
        check([s['source']['repository'].lower() for s in selected] == [f'mainuan/{n}'.lower() for n in names],
              'Lista aprovada e estado anterior divergem.')
        versions = dict(previous['versions']) if previous else {}
        highest = dict(previous['highest']) if previous else {}
        package_names = set()
        for program in selected:
            for p in program['source']['assets']:
                check(p['name'] not in package_names, 'Dois repositórios fornecem o mesmo pacote Debian.')
                package_names.add(p['name'])
                identity = p['name'] + ':' + p['architecture']
                version_key = identity + '=' + p['version']
                check(version_key not in versions or versions[version_key] == p['sha256'],
                      f'{p["name"]}: versão já distribuída com bytes diferentes; publique versão Debian nova.')
                check(p['name'] not in highest or version_compare(p['version'], highest[p['name']]) >= 0,
                      f'{p["name"]}: tentativa de reutilizar versão antiga bloqueada.')
                versions[version_key], highest[p['name']] = p['sha256'], p['version']
        sequence = previous['sequence'] + 1 if previous else 1
        releases = previous['catalog']['releases'] if previous else []
        # A edição editorial só muda se texto ou conjunto de bytes aprovados mudar.
        content = digest(encoded({'selected': selected, 'summary': summary}))
        if not previous or content != previous['content_sha256']:
            features = [{'title': s['title'], 'packages': [
                {'name': p['name'], 'min_version': p['version'], 'architecture': p['architecture'], 'sha256': p['sha256']}
                for p in s['source']['assets']]} for s in selected]
            release = {'id': 'mainuan-recursos', 'version': str(sequence), 'title': 'Novidades do Mainuan',
                       'summary': summary, 'article_url': policy.get('article_url') or selected[0]['article_url'],
                       'features': features, 'sources': [s['source'] for s in selected],
                       'compatibility': {'distro_id': policy['distribution_ids'],
                                         'version_id': policy['distribution_versions'],
                                         'architecture': policy['architectures']}}
            releases = [release] + releases[:49]
        catalog = {'schema_version': 1, 'sequence': sequence, 'published_at': now.isoformat(),
                   'expires_at': (now + timedelta(days=30)).isoformat(), 'releases': releases}
        raw = encoded(catalog)
        parse_catalog(raw, ('github.com',), now, ('https://github.com/mainuan/',))
        signed = signature(raw, key, policy['catalog_key_id'])
        config = Config('https://github.com/mainuan/catalogo', ('github.com',),
                        {policy['catalog_key_id']: policy['catalog_public_key']}, ('https://github.com/mainuan/',))
        authenticate(raw, signed, config, now)
        check(sum(p.stat().st_size for p in pool.iterdir()) <= MAX_POOL, 'Pool APT excede 256 MiB; revise a hospedagem.')
        create_apt(stage, gpg_home, policy['apt_fingerprint'], now, previous_root)
        ledger = {'schema_version': 1, 'sequence': sequence, 'approval_commit': approval_commit,
                  'approval_time': approval_time.isoformat(), 'packages_sha256': digest(packages),
                  'content_sha256': content, 'selected': selected, 'versions': versions, 'highest': highest,
                  'pool': sorted(p.stem for p in pool.iterdir()), 'catalog_sha256': digest(raw)}
        directory = stage / 'catalogo'
        directory.mkdir()
        (directory / 'novidades.json').write_bytes(raw)
        (directory / 'novidades.json.sig').write_bytes(signed)
        state = encoded(ledger)
        state_sig = signature(state, key, policy['catalog_key_id'])
        verify(state, state_sig, policy['catalog_public_key'], policy['catalog_key_id'])
        (directory / 'publicacao.json').write_bytes(state)
        (directory / 'publicacao.json.sig').write_bytes(state_sig)
        stage.rename(output)
    return ledger
