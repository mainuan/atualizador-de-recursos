#!/usr/bin/python3
"""Empacota a release aprovada do gestor para ensaio descartável, sem instalar no host."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mainuan_recursos.catalog import Config, authenticate
from drivers_vm import DEB, SHA, NAME, HOST, ORIGIN, audit_deb, dump, digest


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Diretório novo; nunca /etc ou produção')
    args = parser.parse_args()
    audit = audit_deb(args.deb)
    target = args.output.resolve()
    target.mkdir(parents=True, mode=0o700, exist_ok=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires = now + timedelta(days=2)
    metadata = {'test_only': True, 'id': now.strftime('%Y%m%dT%H%M%SZ'),
                'created_at': now.isoformat(), 'expires_at': expires.isoformat(),
                'package_sha256': SHA, 'package': NAME, 'version': '1.0', 'architecture': 'all',
                'repository': 'mainuan/mainuan-gestao-drivers', 'repository_id': 1405529794,
                'release_id': 421218277, 'asset_id': 667222935,
                'observed_tag_commit': 'd84fdd9c75acca7c69e3e07912f4f0f064b4d1e7',
                'article_url': 'https://github.com/mainuan/mainuan-gestao-drivers/releases/tag/v1.0',
                'upstream_immutable_release': False, 'production_enabled': False,
                'integrity': 'SHA-256 da API GitHub e do SHA256SUMS da release; sem atestação de compilação.',
                'private_signing_keys_discarded': True}
    dump(target / 'auditoria-pacote.json', audit)
    repo = target / 'apt'; (repo / 'pool').mkdir(parents=True)
    shutil.copyfile(args.deb, repo / 'pool' / DEB)
    packages = run(['dpkg-scanpackages', 'pool', '/dev/null'], cwd=repo).stdout
    (repo / 'Packages').write_bytes(packages)
    (repo / 'Packages.gz').write_bytes(gzip.compress(packages, mtime=0))
    release = (f'Origin: {ORIGIN}\nLabel: HOMOLOGACAO DESCARTAVEL — nao producao\n'
               f'Date: {format_datetime(now, usegmt=True)}\nValid-Until: {format_datetime(expires, usegmt=True)}\n'
               'Architectures: amd64 arm64 all\nDescription: Somente Gestao de Drivers 1.0 aprovado\nSHA256:\n')
    for name in ('Packages', 'Packages.gz'):
        data = (repo / name).read_bytes()
        release += f' {hashlib.sha256(data).hexdigest()} {len(data)} {name}\n'
    (repo / 'Release').write_text(release)
    with tempfile.TemporaryDirectory(prefix='mainuan-assinatura-descartavel-') as tmp:
        home = Path(tmp) / 'gnupg'; home.mkdir(mode=0o700)
        gpg = ['gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '']
        try:
            run(gpg + ['--quick-generate-key', 'Mainuan TESTE Gestor 1.0 <teste@example.invalid>', 'ed25519', 'sign', '2d'])
            (target / 'repo-chave-teste.gpg').write_bytes(run(gpg + ['--export']).stdout)
            metadata['apt_key_fingerprint'] = next(line.split(':')[9] for line in
                run(gpg + ['--with-colons', '--list-keys'], text=True).stdout.splitlines() if line.startswith('fpr:'))
            run(gpg + ['--clearsign', '--output', str(repo / 'InRelease'), str(repo / 'Release')])
            run(gpg + ['--detach-sign', '--output', str(repo / 'Release.gpg'), str(repo / 'Release')])
        finally:
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'all'], capture_output=True)
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    config = {'manifest_url': f'https://{HOST}/catalog/novidades.json', 'official_hosts': [HOST, 'github.com'],
              'manifest_prefixes': [f'https://{HOST}/catalog/'], 'article_prefixes': ['https://github.com/mainuan/'],
              'keys': {'descartavel-gestor-vm': public}}
    dump(target / 'config-homologacao.json', config)
    obj = {'schema_version': 1, 'sequence': 1, 'published_at': now.isoformat(), 'expires_at': expires.isoformat(),
           'releases': [{'id': 'homologacao-gestao-drivers', 'version': '1.0', 'title': 'O Mainuan tem novidades!',
             'summary': 'Olá! O Mainuan tem novidades. Confira quais são:\n\nEnsaio controlado: instalar somente o aplicativo Gestão de Drivers. Nenhum driver será instalado ou alterado. Não execute o gestor durante este teste.',
             'article_url': metadata['article_url'],
             'compatibility': {'distro_id': ['mainuan', 'ubuntu'], 'version_id': ['2026', '26.04'], 'architecture': ['amd64', 'arm64']},
             'features': [{'title': 'Gestão de Drivers 1.0', 'packages': [{'name': NAME, 'min_version': '1.0', 'architecture': 'all', 'sha256': SHA}]}],
             'sources': [{'repository': metadata['repository'], 'repository_id': metadata['repository_id'],
                          'release_id': metadata['release_id'], 'commit': metadata['observed_tag_commit'],
                          'assets': [{'asset_id': metadata['asset_id'], 'name': NAME, 'version': '1.0', 'architecture': 'all', 'sha256': SHA}]}]}]}
    raw = json.dumps(obj, ensure_ascii=False, indent=2).encode()
    signature = json.dumps({'key_id': 'descartavel-gestor-vm', 'signature': base64.b64encode(key.sign(raw)).decode()}).encode()
    authenticate(raw, signature, Config.load(target / 'config-homologacao.json'))
    site = target / 'site/catalog'; site.mkdir(parents=True)
    (site / 'novidades.json').write_bytes(raw)
    (site / 'novidades.json.sig').write_bytes(signature)
    spec = importlib.util.spec_from_file_location('vm_kit', Path(__file__).with_name('prepare-vm-kit.py'))
    shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
    shared.write_tls_server(target, now)
    shutil.copyfile(Path(__file__).with_name('drivers_vm.py'), target / 'vm.py')
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'docs/primeiro-teste-drivers-vm.md', target / 'LEIA-ME.md')
    dump(target / 'kit.json', metadata)
    files = sorted(path for path in target.rglob('*') if path.is_file())
    (target / 'ARQUIVOS.sha256').write_text(''.join(f'{digest(path)}  {path.relative_to(target)}\n' for path in files))
    # Contém só uma chave TLS descartável, nunca chaves privadas de assinatura.
    archive = target.with_name(target.name + '.tar.gz')
    if archive.exists():
        raise FileExistsError(archive)
    with tarfile.open(archive, 'x:gz') as stream:
        stream.add(target, arcname=target.name)
    archive.chmod(0o600)
    archive.with_name(archive.name + '.sha256').write_text(f'{digest(archive)}  {archive.name}\n')
    print(json.dumps({'directory': str(target), 'archive': str(archive), **metadata}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
