"""Download e cache autenticado, com fallback offline somente para consulta."""
import base64
import json
from urllib.error import URLError

from .catalog import CatalogError, authenticate, fetch
from .state import atomic_write


class Repository:
    def __init__(self, config, directory, watermark=(0, ""), state=None):
        self.config = config
        self.watermark = watermark
        self.state = state
        self.cache = directory / 'catalog-cache.json'

    def load(self):
        try:
            raw, signature = fetch(self.config)
        except (OSError, URLError):
            if not self.cache.exists():
                raise
            with self.cache.open('rb') as stream:
                encoded = stream.read(3 * 1024 * 1024 + 1)
            if len(encoded) > 3 * 1024 * 1024:
                raise CatalogError('Cache local excede o limite de tamanho.')
            cached = json.loads(encoded)
            raw, signature = (base64.b64decode(cached[k], validate=True) for k in ('catalog', 'signature'))
            catalog = authenticate(raw, signature, self.config)
            self._accept(catalog)
            return catalog, False
        catalog = authenticate(raw, signature, self.config)
        self._accept(catalog)
        # Falhas de assinatura nunca se transformam em fallback offline.
        atomic_write(self.cache, json.dumps({
            'catalog': base64.b64encode(raw).decode(),
            'signature': base64.b64encode(signature).decode(),
        }).encode())
        return catalog, True

    def _accept(self, catalog):
        sequence, digest = self.watermark
        if catalog.sequence < sequence or (catalog.sequence == sequence and catalog.digest != digest):
            raise CatalogError('Catálogo antigo ou alterado; o cache válido foi preservado.')
        if self.state is not None:
            # Persistir antes de tocar no cache ou consultar os pacotes.
            self.state.accept(catalog)
