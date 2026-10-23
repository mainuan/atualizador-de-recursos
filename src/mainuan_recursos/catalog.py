"""Catálogo declarativo autenticado; não contém ações executáveis."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_BYTES = 1024 * 1024
NAME = re.compile(r'[a-z0-9][a-z0-9+.-]+\Z')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,99}\Z')
VERSION = re.compile(r'(?:[0-9]+:)?[0-9][A-Za-z0-9.+~\-]{0,127}\Z')


class CatalogError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CatalogError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'Campo repetido: {key}')
        result[key] = value
    return result


def decode(raw):
    require(len(raw) <= MAX_BYTES, 'Catálogo excede o limite de tamanho.')
    try:
        return json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(CatalogError('Número inválido.')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CatalogError(f'JSON inválido: {exc}') from exc


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), 'Era esperado um objeto JSON.')
    require(set(required) <= obj.keys() and obj.keys() <= set(required) | set(optional),
            'Campos ausentes ou desconhecidos no catálogo/configuração.')


def text(value, maximum=500, multiline=False):
    require(isinstance(value, str) and 0 < len(value) <= maximum
            and not any((ord(c) < 32 and not (multiline and c in '\n\t')) or ord(c) == 127
                        for c in value), 'Texto inválido.')
    return value


def token(value):
    require(isinstance(value, str) and bool(TOKEN.fullmatch(value)), 'Identificador inválido.')
    return value


def https_url(value, hosts):
    text(value, 2048)
    require(value == value.strip() and ' ' not in value, 'Endereço HTTPS contém espaços.')
    try:
        url = urlsplit(value)
        require(url.scheme == 'https' and url.hostname in hosts and url.port in (None, 443)
                and not url.username and not url.password and not url.fragment
                and '\\' not in value, 'Endereço fora dos domínios HTTPS oficiais configurados.')
    except ValueError as exc:
        raise CatalogError('Endereço HTTPS inválido.') from exc
    return value


def scoped_url(value, prefixes):
    """Prefixos HTTPS com limite de segmento e caminho sem normalização ambígua."""
    hosts = tuple(urlsplit(prefix).hostname for prefix in prefixes)
    https_url(value, hosts)
    url = urlsplit(value)
    require('%' not in url.path and not any(part in ('.', '..') for part in url.path.split('/'))
            and '//' not in url.path, 'Caminho de URL ambíguo ou não permitido.')
    allowed = False
    for prefix in prefixes:
        scope = urlsplit(prefix)
        if url.hostname == scope.hostname and (url.path == scope.path.rstrip('/') or url.path.startswith(scope.path)):
            allowed = True
    require(allowed, 'O caminho da URL não pertence à infraestrutura oficial autorizada.')
    return value


def validate_prefixes(values):
    require(isinstance(values, (list, tuple)) and 0 < len(values) <= 20, 'Configure os prefixos oficiais de URL.')
    for value in values:
        url = urlsplit(value)
        https_url(value, (url.hostname,))
        require(url.hostname and url.path.startswith('/') and url.path.endswith('/')
                and not url.query and not url.fragment, 'Prefixo oficial inválido; use HTTPS e caminho terminado em /.')
        scoped_url(value, (value,))
    return tuple(values)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.utcoffset() == timedelta(0), 'Use datas UTC com sufixo Z.')
        return parsed
    except (ValueError, TypeError, AttributeError) as exc:
        raise CatalogError('Data inválida.') from exc


@dataclass(frozen=True)
class Package:
    name: str
    min_version: str
    architecture: str = ''
    sha256: str = ''


@dataclass(frozen=True)
class Feature:
    title: str
    packages: tuple[Package, ...]


@dataclass(frozen=True)
class Release:
    id: str
    version: str
    title: str
    summary: str
    article_url: str
    features: tuple[Feature, ...]
    compatibility: dict

    @property
    def key(self):
        return f'{self.id}@{self.version}'

    @property
    def packages(self):
        return tuple(p for f in self.features for p in f.packages)

    def compatible(self, system):
        return all(system.get(k) in values for k, values in self.compatibility.items())


@dataclass(frozen=True)
class Catalog:
    sequence: int
    expires_at: datetime
    releases: tuple[Release, ...]
    digest: str


@dataclass(frozen=True)
class Config:
    manifest_url: str
    official_hosts: tuple[str, ...]
    keys: dict[str, str]
    article_prefixes: tuple[str, ...] = ('https://mainuan.example/',)
    manifest_prefixes: tuple[str, ...] = ('https://mainuan.example/',)

    @classmethod
    def load(cls, path=Path('/etc/mainuan/atualizador-recursos.json')):
        with path.open('rb') as stream:
            obj = decode(stream.read(MAX_BYTES + 1))
        fields(obj, ('manifest_url', 'official_hosts', 'article_prefixes', 'manifest_prefixes', 'keys'))
        hosts = obj['official_hosts']
        require(isinstance(hosts, list) and bool(hosts) and all(
            isinstance(h, str) and re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', h) for h in hosts),
            'Configure os domínios oficiais do Mainuan em /etc/mainuan/atualizador-recursos.json.')
        articles = validate_prefixes(obj['article_prefixes'])
        manifests = validate_prefixes(obj['manifest_prefixes'])
        scoped_url(obj['manifest_url'], manifests)
        require(not urlsplit(obj['manifest_url']).query, 'A URL do catálogo não pode conter consulta.')
        require(isinstance(obj['keys'], dict) and bool(obj['keys']), 'Instale a chave pública oficial do catálogo.')
        for key_id, key in obj['keys'].items():
            token(key_id)
            try:
                require(len(base64.b64decode(key, validate=True)) == 32, 'Chave Ed25519 inválida.')
            except (ValueError, TypeError) as exc:
                raise CatalogError('Chave pública inválida.') from exc
        return cls(https_url(obj['manifest_url'], hosts), tuple(hosts), obj['keys'], articles, manifests)


def parse_catalog(raw, hosts, now=None, article_prefixes=None):
    now = now or datetime.now(timezone.utc)
    obj = decode(raw)
    fields(obj, ('schema_version', 'sequence', 'published_at', 'expires_at', 'releases'))
    require(type(obj['schema_version']) is int and obj['schema_version'] == 1, 'Esquema não suportado.')
    require(type(obj['sequence']) is int and 0 < obj['sequence'] < 2**53, 'Sequência inválida.')
    published, expires = timestamp(obj['published_at']), timestamp(obj['expires_at'])
    require(published <= now + timedelta(minutes=5) and published < expires
            and now < expires <= published + timedelta(days=31), 'Catálogo expirado ou com validade inválida.')
    require(isinstance(obj['releases'], list) and len(obj['releases']) <= 200, 'Lista de lançamentos inválida.')
    releases, seen = [], set()
    for item in obj['releases']:
        fields(item, ('id', 'version', 'title', 'summary', 'features'),
               ('article_url', 'compatibility', 'sources'))
        release_id, version = token(item['id']), token(item['version'])
        key = (release_id, version)
        require(key not in seen, 'Lançamento duplicado.')
        seen.add(key)
        compat = item.get('compatibility', {})
        fields(compat, (), ('distro_id', 'version_id', 'architecture'))
        for values in compat.values():
            require(isinstance(values, list) and 0 < len(values) <= 20, 'Compatibilidade inválida.')
            for value in values:
                token(value)
        features, names = [], set()
        require(isinstance(item['features'], list) and 0 < len(item['features']) <= 50, 'Recursos inválidos.')
        for feature in item['features']:
            fields(feature, ('title', 'packages'))
            require(isinstance(feature['packages'], list) and 0 < len(feature['packages']) <= 50,
                    'Pacotes inválidos.')
            packages = []
            for package in feature['packages']:
                fields(package, ('name', 'min_version'), ('architecture', 'sha256'))
                name, minimum = package['name'], package['min_version']
                require(isinstance(name, str) and len(name) <= 100 and bool(NAME.fullmatch(name))
                        and name not in names, 'Nome de pacote inválido ou repetido.')
                require(isinstance(minimum, str) and len(minimum) <= 128
                        and not minimum.endswith('-') and bool(VERSION.fullmatch(minimum)), 'Versão Debian inválida.')
                names.add(name)
                arch, digest = package.get('architecture', ''), package.get('sha256', '')
                require(('architecture' in package) == ('sha256' in package), 'Pin incompleto do pacote.')
                if 'architecture' in package:
                    require(isinstance(arch, str) and bool(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,30}', arch))
                            and isinstance(digest, str) and bool(re.fullmatch(r'[0-9a-f]{64}', digest)),
                            'Arquitetura ou SHA-256 inválido.')
                packages.append(Package(name, minimum, arch, digest))
            features.append(Feature(text(feature['title'], 150), tuple(packages)))
        sources = item.get('sources', [])
        require(isinstance(sources, list) and len(sources) <= 50, 'Proveniência inválida.')
        source_packages = []
        for source in sources:
            fields(source, ('repository', 'repository_id', 'release_id', 'commit', 'assets'))
            require(isinstance(source['repository'], str) and bool(re.fullmatch(
                r'mainuan/[A-Za-z0-9][A-Za-z0-9._-]{0,99}', source['repository'])), 'Origem GitHub inválida.')
            require(all(type(source[k]) is int and source[k] > 0 for k in ('repository_id', 'release_id'))
                    and isinstance(source['commit'], str) and bool(re.fullmatch(r'[0-9a-f]{40}', source['commit'])),
                    'Referência imutável inválida.')
            require(isinstance(source['assets'], list) and 0 < len(source['assets']) <= 50, 'Artefatos inválidos.')
            for asset in source['assets']:
                fields(asset, ('asset_id', 'name', 'version', 'architecture', 'sha256'))
                require(type(asset['asset_id']) is int and asset['asset_id'] > 0, 'ID de artefato inválido.')
                source_packages.append((asset['name'], asset['version'], asset['architecture'], asset['sha256']))
        if sources:
            pins = [(p.name, p.min_version, p.architecture, p.sha256) for f in features for p in f.packages]
            require(sorted(source_packages) == sorted(pins), 'Proveniência diverge dos pacotes oferecidos.')
        fallback = ('https://github.com/' + sources[0]['repository'] + '/releases' if sources else
                    'https://github.com/mainuan/atualizadorderecursos/releases')
        article = https_url(item.get('article_url') or fallback, hosts)
        if article_prefixes is not None:
            scoped_url(article, article_prefixes)
        releases.append(Release(release_id, version, text(item['title'], 150), text(item['summary'], 2000, multiline=True),
                                article, tuple(features), compat))
    return Catalog(obj['sequence'], expires, tuple(releases), hashlib.sha256(raw).hexdigest())


def authenticate(raw, signature, config, now=None):
    require(len(raw) <= MAX_BYTES, 'Catálogo excede o limite de tamanho.')
    envelope = decode(signature)
    fields(envelope, ('key_id', 'signature'))
    try:
        key = config.keys[envelope['key_id']]
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True)).verify(
            base64.b64decode(envelope['signature'], validate=True), raw)
    except Exception as exc:
        raise CatalogError('A assinatura do catálogo não é válida ou a chave não é confiável.') from exc
    return parse_catalog(raw, config.official_hosts, now, config.article_prefixes)


class OfficialRedirects(HTTPRedirectHandler):
    def __init__(self, hosts, prefixes=None):
        super().__init__()
        self.hosts = hosts
        self.prefixes = prefixes

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        https_url(newurl, self.hosts)
        if self.prefixes:
            scoped_url(newurl, self.prefixes)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, config):
    https_url(url, config.official_hosts)
    scoped_url(url, config.manifest_prefixes)
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), OfficialRedirects(config.official_hosts, config.manifest_prefixes))
    with opener.open(Request(url, headers={'User-Agent': 'Mainuan-Recursos/0.2', 'Accept': 'application/json'}), timeout=15) as response:
        data = response.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, 'Resposta excede o limite de tamanho.')
    return data


def fetch(config):
    return download(config.manifest_url, config), download(config.manifest_url + '.sig', config)
