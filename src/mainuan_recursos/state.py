"""Estado editorial e observação de pacotes, separados por lançamento."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
from threading import RLock
import time

from .catalog import CatalogError, require, unique_object


def atomic_write(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.recursos-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Torna também a troca de nome durável antes de aceitar a publicação.
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class State:
    def __init__(self, path=None):
        self.path = path
        self.lock = RLock()
        self.data = {'releases': {}, 'sequence': 0, 'digest': ''}
        if path and path.exists():
            try:
                with path.open('rb') as stream:
                    raw = stream.read(8 * 1024 * 1024 + 1)
                require(len(raw) <= 8 * 1024 * 1024, 'Estado local muito grande.')
                obj = json.loads(raw, object_pairs_hook=unique_object)
                require(isinstance(obj, dict) and set(obj) == {'releases', 'sequence', 'digest'}, 'Estado inválido.')
                require(isinstance(obj['releases'], dict) and type(obj['sequence']) is int
                        and obj['sequence'] >= 0 and isinstance(obj['digest'], str), 'Estado inválido.')
                require((obj['sequence'] == 0 and obj['digest'] == '') or
                        (obj['sequence'] > 0 and len(obj['digest']) == 64
                         and all(c in '0123456789abcdef' for c in obj['digest'])), 'Sequência/digest inválidos.')
                for key, entry in obj['releases'].items():
                    require(isinstance(key, str) and isinstance(entry, dict), 'Lançamento inválido.')
                    require(set(entry) == {'presentation', 'packages', 'postponed_until'}, 'Estado incompleto.')
                    require(entry['presentation'] in ('unseen', 'viewed', 'postponed')
                            and entry['packages'] in ('unknown', 'pending', 'installed'), 'Estado inválido.')
                    until = entry['postponed_until']
                    require(type(until) in (int, float) and math.isfinite(until) and until >= 0, 'Prazo inválido.')
                self.data = obj
            except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
                raise CatalogError('O estado local está danificado. Preserve o arquivo antes de recuperá-lo.') from exc

    def save(self):
        with self.lock:
            if self.path:
                atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, allow_nan=False).encode())

    def _change(self, update):
        with self.lock:
            previous = deepcopy(self.data)
            update()
            if self.data == previous:
                return
            try:
                self.save()
            except OSError:
                self.data = previous
                # A troca de nome pode ter ocorrido antes de uma falha no fsync.
                if self.path and self.path.exists():
                    try:
                        self.data = State(self.path).data
                    except (OSError, CatalogError):
                        pass
                raise

    def accept(self, catalog):
        def update():
            if catalog.sequence < self.data['sequence'] or (
                catalog.sequence == self.data['sequence'] and catalog.digest != self.data['digest']
            ):
                raise CatalogError('Catálogo antigo ou conteúdo alterado sem aumentar a sequência.')
            self.data.update(sequence=catalog.sequence, digest=catalog.digest)
        self._change(update)

    def entry(self, release):
        with self.lock:
            return self.data['releases'].setdefault(release.key, {
                'presentation': 'unseen', 'postponed_until': 0, 'packages': 'unknown'})

    def due(self, release, now=None):
        with self.lock:
            entry = self.entry(release)
            return entry['presentation'] == 'unseen' or (
                entry['presentation'] == 'postponed' and entry['postponed_until'] <= (time.time() if now is None else now))

    def viewed(self, release):
        def update():
            entry = self.entry(release)
            # Consulta manual antes do prazo não cancela o adiamento solicitado.
            if entry['presentation'] != 'postponed' or entry['postponed_until'] <= time.time():
                entry['presentation'] = 'viewed'
        self._change(update)

    def postpone(self, release, now=None):
        self._change(lambda: self.entry(release).update(
            presentation='postponed', postponed_until=(time.time() if now is None else now) + 86400))

    def observe(self, release, plan):
        self._change(lambda: self.entry(release).update(packages='installed' if plan.complete else 'pending'))


def state_directory():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'mainuan-recursos'
