#!/usr/bin/python3
"""Publicação de produção: exige configuração e chaves fornecidas pela equipe."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from publication import GitHub, PublicationError, check, publish
from mainuan_recursos.catalog import CatalogError, Config
from publication_verify import verify_publication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--refresh', action='store_true', help='aprovação explícita de novas releases')
    args = parser.parse_args()
    root = args.root.resolve()
    check(os.environ.get('GITHUB_REPOSITORY') == 'mainuan/atualizadorderecursos'
          and os.environ.get('GITHUB_REF') == 'refs/heads/main'
          and os.environ.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch', 'schedule'),
          'Publicação só pode ocorrer no workflow autorizado da branch main oficial.')
    check(not args.refresh or os.environ['GITHUB_EVENT_NAME'] == 'workflow_dispatch',
          'Refresh explícito exige workflow_dispatch.')
    with (root / 'publication.toml').open('rb') as stream:
        policy = tomllib.load(stream)
    check(policy.get('enabled') is True, 'Produção desativada em publication.toml.')
    ed_key = os.environ.pop('CATALOG_PRIVATE_KEY', '').encode()
    apt_key = os.environ.pop('APT_PRIVATE_KEY', '').encode()
    check(ed_key and apt_key, 'Chaves oficiais ausentes; nada será publicado.')
    sha = os.environ['GITHUB_SHA']
    check(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == sha,
          'Checkout diferente do commit autorizado.')
    now = datetime.now(timezone.utc)
    # Um retry de push mantém o instante original de aprovação. Artefatos posteriores falham.
    approved_at = (datetime.fromisoformat(subprocess.check_output(
        ['git', 'show', '-s', '--format=%cI', sha], cwd=root, text=True).strip()).astimezone(timezone.utc)
        if os.environ['GITHUB_EVENT_NAME'] == 'push' else now)
    with tempfile.TemporaryDirectory(prefix='mainuan-assinatura-') as temp:
        gpg_home = Path(temp)
        gpg_home.chmod(0o700)
        try:
            result = subprocess.run(['gpg', '--homedir', temp, '--batch', '--import'], input=apt_key,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            check(result.returncode == 0, 'Falha ao importar chave APT protegida.')
            result = publish((root / 'packages.txt').read_bytes(), (root / 'message.txt').read_bytes(),
                             policy=policy, github=GitHub(os.environ.get('GITHUB_TOKEN', '')),
                             previous_root=root, output=args.output.resolve(), private_key=ed_key,
                             gpg_home=gpg_home, approval_commit=sha, approval_time=approved_at,
                             now=now, refresh=args.refresh)
            public_keyring = gpg_home / 'apt-publico.gpg'
            public_keyring.write_bytes(subprocess.check_output(
                ['gpg', '--homedir', temp, '--batch', '--export', policy['apt_fingerprint']],
                stderr=subprocess.DEVNULL))
            public_keys = dict(policy.get('previous_catalog_keys', {}))
            public_keys[policy['catalog_key_id']] = policy['catalog_public_key']
            config = Config('https://github.com/mainuan/catalogo', ('github.com',), public_keys,
                            ('https://github.com/mainuan/',))
            verify_publication(args.output.resolve(), config, public_keyring)
        finally:
            subprocess.run(['gpgconf', '--homedir', temp, '--kill', 'all'], capture_output=True)
    print(f'Publicação validada: sequência {result["sequence"]}; {len(result["selected"])} programa(s).')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Exceções HTTP/CDN podem conter URLs temporárias assinadas; não imprimi-las.
        print('Erro: ' + (str(exc) if isinstance(exc, (PublicationError, CatalogError)) else
                         f'{type(exc).__name__}: publicação abortada; revise entradas e configuração.'), file=sys.stderr)
        raise SystemExit(1)
