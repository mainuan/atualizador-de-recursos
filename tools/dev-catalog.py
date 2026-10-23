#!/usr/bin/python3
"""Cria catálogo e chaves descartáveis de teste fora da configuração de produção."""
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mainuan_recursos.catalog import Config, authenticate


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Uso: /usr/bin/python3 tools/dev-catalog.py DIRETORIO_NOVO')
    target = Path(sys.argv[1]).resolve()
    target.mkdir(mode=0o700)  # Recusa sobrescrever diretório existente.
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    with os.fdopen(os.open(target / 'test-private.pem', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        output.write(private)
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    obj = json.loads((Path(__file__).resolve().parents[1] / 'examples/catalog.json').read_text())
    now = datetime.now(timezone.utc).replace(microsecond=0)
    obj.update(published_at=now.isoformat(), expires_at=(now + timedelta(days=7)).isoformat())
    raw = json.dumps(obj, ensure_ascii=False, indent=2).encode()
    signature = json.dumps({'key_id':'teste-descartavel', 'signature':base64.b64encode(key.sign(raw)).decode()}).encode()
    config = {'manifest_url':'https://mainuan.example/recursos/catalog.json','official_hosts':['mainuan.example'],
              'manifest_prefixes':['https://mainuan.example/recursos/'],'article_prefixes':['https://mainuan.example/'],
              'keys':{'teste-descartavel':public}}
    (target / 'catalog.json').write_bytes(raw)
    (target / 'catalog.json.sig').write_bytes(signature)
    (target / 'config.json').write_text(json.dumps(config, indent=2))
    authenticate(raw, signature, Config.load(target / 'config.json'))
    print(f'Catálogo e chave fictícios gerados e validados em {target}. Não use em produção.')


if __name__ == '__main__':
    main()
