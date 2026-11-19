"""Preferência do usuário: mostrar ou não novidades automaticamente ao entrar.

Fica em ``$XDG_CONFIG_HOME/mainuan-recursos/preferences.json`` (padrão
``~/.config``).  Desligada, a verificação do autostart (``--check``) encerra
antes de consultar a rede; a abertura manual continua funcionando.
"""
import json
import os
from pathlib import Path

from .state import atomic_write

MAX_BYTES = 4096


def config_directory():
    return Path(os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')) / 'mainuan-recursos'


class Preferences:
    def __init__(self, path=None):
        self.path = path or config_directory() / 'preferences.json'
        self.automatic = True
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            obj = json.loads(raw) if len(raw) <= MAX_BYTES else None
            if isinstance(obj, dict) and set(obj) == {'automatic_news'} and type(obj['automatic_news']) is bool:
                self.automatic = obj['automatic_news']
        except (OSError, ValueError):
            # Sem arquivo ou arquivo ilegível: vale o padrão (novidades ligadas).
            pass

    def set_automatic(self, value):
        atomic_write(self.path, json.dumps({'automatic_news': bool(value)}).encode())
        self.automatic = bool(value)
