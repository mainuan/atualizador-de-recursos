#!/usr/bin/python3
"""Ferramenta editorial offline. A chave privada nunca é enviada ao aplicativo."""
import argparse
import base64
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mainuan_recursos.catalog import Config, authenticate, parse_catalog, token
from mainuan_recursos.state import atomic_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    gen = sub.add_parser('keygen', help='gerar chave de homologação ou produção em local seguro')
    gen.add_argument('--private-key', type=Path, required=True)
    sign = sub.add_parser('sign', help='validar e assinar os bytes do catálogo')
    sign.add_argument('catalog', type=Path)
    sign.add_argument('--private-key', type=Path, required=True)
    sign.add_argument('--key-id', required=True)
    sign.add_argument('--config', type=Path, required=True)
    verify = sub.add_parser('verify', help='validar localmente o par catálogo/assinatura')
    verify.add_argument('catalog', type=Path)
    verify.add_argument('--config', type=Path, required=True)
    opts = parser.parse_args()
    if opts.action == 'keygen':
        key = Ed25519PrivateKey.generate()
        fd = os.open(opts.private_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
        print(base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,
                                                           serialization.PublicFormat.Raw)).decode())
    elif opts.action == 'sign':
        token(opts.key_id)
        raw = opts.catalog.read_bytes()
        config = Config.load(opts.config)
        parse_catalog(raw, config.official_hosts, article_prefixes=config.article_prefixes)
        key = serialization.load_pem_private_key(opts.private_key.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError('Use uma chave Ed25519.')
        signature = {'key_id': opts.key_id, 'signature': base64.b64encode(key.sign(raw)).decode()}
        encoded = json.dumps(signature).encode()
        authenticate(raw, encoded, config)
        atomic_write(Path(str(opts.catalog) + '.sig'), encoded)
        print('Catálogo validado e assinatura criada. Publique ambos sem alterar os bytes.')
    else:
        catalog = authenticate(opts.catalog.read_bytes(), Path(str(opts.catalog) + '.sig').read_bytes(), Config.load(opts.config))
        print(f'Assinatura válida. Sequência {catalog.sequence}; {len(catalog.releases)} lançamento(s).')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        raise SystemExit(1)
