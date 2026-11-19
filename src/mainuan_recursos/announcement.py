"""Anúncio editorial explícito: ``announcements.json`` no repositório oficial.

A janela automática só existe para um anúncio publicado de propósito: arquivo
válido, ``"enabled": true``, identificador e versão válidos, textos curtos em
texto simples e aplicável a este sistema.  Uma release de programa, o
``packages.txt`` ou o ``message.txt`` (canal das versões ≤ 0.3.1) nunca são
anúncios por si sós.

O arquivo é só dados: nenhum campo é executado, interpretado como HTML ou
instala algo.  ``packages`` apenas sugere repositórios oficiais; a instalação
continua exigindo o clique do usuário e todas as verificações do canal.
"""
from dataclasses import dataclass
import json
import re

from .catalog import CatalogError, decode, require, scoped_url, text, token
from .i18n import _, message_languages

FILENAME = 'announcements.json'
MAX_BYTES = 64 * 1024
SCHEMA = 1
SOURCE_LANGUAGE = 'pt_BR'
ID = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z')
LANGUAGE = re.compile(r'[a-z]{2,3}(?:_[A-Z]{2})?\Z')
REPOSITORY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')
# Únicos destinos aceitos para o botão "Conhecer novidades".
URL_PREFIXES = ('https://github.com/mainuan/', 'https://mainuan.github.io/')
FIELDS = ('schema', 'enabled', 'id', 'version', 'title', 'message', 'url', 'packages', 'applies_to')
APPLIES_TO = ('distro_id', 'version_id', 'architecture')
MAX_TITLE = 150
MAX_MESSAGE = 2000
MAX_VERSION = 2 ** 31 - 1


def invalid():
    return CatalogError(_('announcements.json is invalid or incomplete.'))


@dataclass(frozen=True)
class Announcement:
    id: str
    version: int
    titles: tuple          # ((idioma, título), ...) em ordem alfabética
    messages: tuple        # ((idioma, mensagem), ...) em ordem alfabética
    url: str = ''
    packages: tuple = ()
    applies_to: tuple = ()  # ((campo, (valores, ...)), ...)

    @property
    def key(self):
        """Chave do estado local: um novo número de versão é um novo anúncio."""
        return f'{self.id}@{self.version}'

    def canonical(self):
        """Conteúdo completo (todos os idiomas), base do digest da edição."""
        return {'id': self.id, 'version': self.version, 'title': dict(self.titles),
                'message': dict(self.messages), 'url': self.url, 'packages': list(self.packages),
                'applies_to': {k: list(v) for k, v in self.applies_to}}

    def filters(self):
        return {k: list(v) for k, v in self.applies_to}

    def applies(self, system):
        """Campos opcionais de ``applies_to`` comparados com o os-release/dpkg."""
        return all(system.get(k) in values for k, values in self.applies_to)

    def language(self, languages=None):
        """Idioma da sessão; depois inglês; por fim o português do Brasil."""
        titles = dict(self.titles)
        for candidate in (message_languages() if languages is None else languages):
            if candidate in titles:
                return candidate
            if candidate == 'pt' and SOURCE_LANGUAGE in titles:
                return SOURCE_LANGUAGE
        return 'en' if 'en' in titles else SOURCE_LANGUAGE

    def localized(self, languages=None):
        """Título e texto para a janela, como texto simples."""
        language = self.language(languages)
        title = dict(self.titles)[language]
        message = dict(self.messages).get(language, '')
        return title, (f'{title}\n\n{message}' if message else title)


def _texts(value, maximum, multiline):
    require(isinstance(value, dict) and 0 < len(value) <= 40, _('announcements.json is invalid or incomplete.'))
    result = {}
    for language, content in value.items():
        require(isinstance(language, str) and bool(LANGUAGE.fullmatch(language)),
                _('announcements.json is invalid or incomplete.'))
        require(isinstance(content, str), _('announcements.json is invalid or incomplete.'))
        result[language] = text(content.replace('\r\n', '\n').strip(), maximum, multiline)
    return result


def parse(raw):
    """Valida o arquivo publicado.  ``None``: nenhum anúncio ativo."""
    require(isinstance(raw, (bytes, bytearray)) and len(raw) <= MAX_BYTES,
            _('announcements.json exceeds the allowed size.'))
    try:
        raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise invalid() from exc
    obj = decode(bytes(raw))
    require(isinstance(obj, dict) and {'schema', 'enabled'} <= obj.keys() and obj.keys() <= set(FIELDS),
            _('announcements.json is invalid or incomplete.'))
    require(type(obj['schema']) is int and obj['schema'] == SCHEMA,
            _('announcements.json uses an unsupported format. Update the application.'))
    require(type(obj['enabled']) is bool, _('announcements.json is invalid or incomplete.'))
    if not obj['enabled']:
        # Desativado: os demais campos podem ser rascunho e não são exibidos.
        return None
    require({'id', 'version', 'title'} <= obj.keys(), _('announcements.json is invalid or incomplete.'))
    announcement_id = obj['id']
    require(isinstance(announcement_id, str) and bool(ID.fullmatch(announcement_id))
            and announcement_id != 'github', _('Invalid announcement identifier.'))
    version = obj['version']
    require(type(version) is int and 0 < version <= MAX_VERSION, _('Invalid announcement version.'))
    titles = _texts(obj['title'], MAX_TITLE, False)
    message = obj.get('message', {})
    messages = {} if message == {} else _texts(message, MAX_MESSAGE, True)
    require(SOURCE_LANGUAGE in titles and (not messages or SOURCE_LANGUAGE in messages)
            and set(messages) <= set(titles),
            _('The announcement needs its text in Brazilian Portuguese (pt_BR).'))
    url = obj.get('url', '')
    require(isinstance(url, str), _('announcements.json is invalid or incomplete.'))
    if url:
        scoped_url(url, URL_PREFIXES)
    packages = obj.get('packages', [])
    require(isinstance(packages, list) and len(packages) <= 20 and len(set(map(str, packages))) == len(packages)
            and all(isinstance(p, str) and REPOSITORY.fullmatch(p) and p not in ('.', '..') for p in packages),
            _('announcements.json lists invalid or repeated repositories.'))
    applies = obj.get('applies_to', {})
    require(isinstance(applies, dict) and applies.keys() <= set(APPLIES_TO),
            _('announcements.json is invalid or incomplete.'))
    filters = []
    for field in sorted(applies):
        values = applies[field]
        require(isinstance(values, list) and 0 < len(values) <= 20 and len(set(map(str, values))) == len(values),
                _('announcements.json is invalid or incomplete.'))
        filters.append((field, tuple(token(v) for v in values)))
    return Announcement(announcement_id, version, tuple(sorted(titles.items())), tuple(sorted(messages.items())),
                        url, tuple(packages), tuple(filters))


def digest_content(announcement):
    """Representação estável para o digest da edição (``None`` sem anúncio)."""
    return json.dumps(announcement.canonical() if announcement else None, sort_keys=True, ensure_ascii=False)
