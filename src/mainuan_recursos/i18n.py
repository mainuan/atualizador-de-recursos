"""Gettext catalog of the application.

The domain is the Debian package name.  The language follows the session
(LANGUAGE, LC_ALL, LC_MESSAGES, LANG); nothing here forces a language.
Catalogs are looked up in:

1. ``$MAINUAN_RECURSOS_LOCALEDIR`` when set (tests, local builds);
2. ``<source tree>/build/locale`` when running from a checkout
   (``po/i18n.sh compile build/locale``);
3. ``/usr/share/locale`` (installed package).
"""
import gettext as _gettext
import os
import re
from pathlib import Path

DOMAIN = 'mainuan-atualizador-recursos'
LOCALEDIR_ENV = 'MAINUAN_RECURSOS_LOCALEDIR'
SYSTEM_LOCALEDIR = '/usr/share/locale'

_translation = None


def localedirs():
    configured = os.environ.get(LOCALEDIR_ENV)
    if configured:
        return [configured]
    directories = []
    source = Path(__file__).resolve().parents[2]
    if (source / 'po' / 'LINGUAS').is_file():
        directories.append(str(source / 'build' / 'locale'))
    directories.append(SYSTEM_LOCALEDIR)
    return directories


def translation():
    global _translation
    if _translation is None:
        result = _gettext.NullTranslations()
        for directory in localedirs():
            if _gettext.find(DOMAIN, directory):
                result = _gettext.translation(DOMAIN, directory, fallback=True)
                break
        _translation = result
    return _translation


def reload():
    """Forget the loaded catalog; the next lookup reads the environment again."""
    global _translation
    _translation = None


def _(message):
    return translation().gettext(message)


def ngettext(singular, plural, n):
    return translation().ngettext(singular, plural, n)


def pgettext(context, message):
    return translation().pgettext(context, message)


def N_(message):
    """Mark a string for extraction; translate it later with _()."""
    return message


def message_languages():
    """Session languages for remote texts, most specific first.

    Same variables and order as gettext: ``LANGUAGE=en_US:pt_BR`` with
    ``LANG=en_US.UTF-8`` gives ``['en_US', 'en', 'pt_BR', 'pt']``.  The C and
    POSIX locales give an empty list.
    """
    names = []
    for variable in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        value = os.environ.get(variable)
        if value:
            names = value.split(':')
            break
    result = []
    for name in names:
        name = name.split('.', 1)[0].split('@', 1)[0]
        if not name or name in ('C', 'POSIX'):
            continue
        language = name.split('_', 1)[0]
        for candidate in (name, language):
            if re.fullmatch(r'[a-z]{2,3}(?:_[A-Z]{2})?', candidate) and candidate not in result:
                result.append(candidate)
    return result[:6]
