#!/usr/bin/python3
"""Audita uma árvore publicada usando somente as duas chaves públicas confiáveis."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import gzip
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mainuan_recursos.catalog import Config, authenticate
from publication import PublicationError, check, digest, inspect_deb, read_json, verify


def bounded(path, maximum):
    check(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
          f'Arquivo ausente, inseguro ou excessivo: {path.name}.')
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    check(len(raw) <= maximum, f'Arquivo excessivo: {path.name}.')
    return raw


def verify_publication(root, config, apt_keyring, now=None):
    import apt_pkg
    now = now or datetime.now(timezone.utc)
    cat_path = root / 'catalogo/novidades.json'
    raw = bounded(cat_path, 1024 * 1024)
    catalog = authenticate(raw, bounded(Path(str(cat_path) + '.sig'), 16384), config, now)
    ledger_raw = bounded(root / 'catalogo/publicacao.json', 8 * 1024 * 1024)
    envelope = bounded(root / 'catalogo/publicacao.json.sig', 16384)
    key_id = read_json(envelope).get('key_id')
    check(key_id in config.keys, 'Chave do registro de publicação não autorizada.')
    verify(ledger_raw, envelope, config.keys[key_id], key_id)
    ledger = read_json(ledger_raw)
    check(ledger['catalog_sha256'] == catalog.digest and ledger['sequence'] == catalog.sequence,
          'Registro e catálogo não pertencem à mesma edição.')
    apt = root / 'apt'
    release = bounded(apt / 'Release', 1024 * 1024)
    for name in ('InRelease', 'Release.gpg'):
        bounded(apt / name, 2 * 1024 * 1024)
    with tempfile.TemporaryDirectory(prefix='mainuan-verificar-publicacao-') as temp:
        home = Path(temp)
        clear = home / 'Release-verificado'
        args = ['gpgv', '--homedir', temp, '--keyring', str(apt_keyring.resolve())]
        for operation in (['--output', str(clear), str(apt / 'InRelease')],
                          [str(apt / 'Release.gpg'), str(apt / 'Release')]):
            result = subprocess.run(args + operation, capture_output=True, timeout=30)
            check(result.returncode == 0, 'Assinatura APT inválida ou chave pública não autorizada.')
        check(clear.read_bytes() == release, 'InRelease e Release divergem.')
    section = apt_pkg.TagSection(release.decode())
    expires = parsedate_to_datetime(section['Valid-Until'])
    published = parsedate_to_datetime(section['Date'])
    check(published <= now and now < expires, 'Metadados APT expirados ou com data futura.')
    checksums = {}
    for line in section['SHA256'].splitlines():
        if not line.strip():
            continue
        sha, length, name = line.split()
        check(name in ('Packages', 'Packages.gz') and name not in checksums,
              'Lista de índices APT inválida.')
        data = bounded(apt / name, 8 * 1024 * 1024)
        check(digest(data) == sha and len(data) == int(length), 'Índice APT adulterado.')
        by_hash = bounded(apt / 'by-hash/SHA256' / sha, 8 * 1024 * 1024)
        check(by_hash == data, 'Índice APT por hash ausente ou divergente.')
        checksums[name] = data
    check(set(checksums) == {'Packages', 'Packages.gz'}, 'Índices APT incompletos.')
    # A saída descomprimida é limitada antes de ler o conteúdo integralmente.
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(checksums['Packages.gz'])) as stream:
        inflated = stream.read(8 * 1024 * 1024 + 1)
    check(inflated == checksums['Packages'], 'Packages e Packages.gz divergem.')
    available, seen, total = set(), set(), 0
    for paragraph in checksums['Packages'].decode().strip().split('\n\n'):
        check(bool(paragraph), 'Índice APT vazio.')
        item = apt_pkg.TagSection(paragraph + '\n\n')
        filename, sha = item['Filename'], item['SHA256']
        check(bool(re.fullmatch(r'pool/[0-9a-f]{64}\.deb', filename))
              and filename == f'pool/{sha}.deb' and sha not in seen, 'Caminho ou SHA de pacote inválido.')
        path = apt / filename
        data = bounded(path, 25 * 1024 * 1024)
        total += len(data)
        check(total <= 256 * 1024 * 1024, 'Pool APT excede o limite.')
        check(digest(data) == sha and len(data) == int(item['Size']), 'Pacote adulterado ou truncado.')
        control = inspect_deb(path)
        check((item['Package'], item['Version'], item['Architecture']) ==
              (control['name'], control['version'], control['architecture']),
              'Control Debian e índice APT divergem.')
        available.add((control['name'], control['version'], control['architecture'], sha))
        seen.add(sha)
    check(seen == set(ledger['pool']) and len(ledger['pool']) == len(seen),
          'Pool APT e registro assinado divergem.')
    actual_pool = {p.name for p in (apt / 'pool').iterdir()}
    check(actual_pool == {sha + '.deb' for sha in seen}, 'Pool contém arquivos ausentes ou não registrados.')
    for release_item in catalog.releases:
        for package in release_item.packages:
            check(package.sha256 and (package.name, package.min_version, package.architecture, package.sha256) in available,
                  'Pacote do catálogo não está presente com os mesmos bytes no APT.')
    for program in ledger['selected']:
        for p in program['source']['assets']:
            check((p['name'], p['version'], p['architecture'], p['sha256']) in available,
                  'Seleção aprovada não está disponível no APT.')
    return {'sequence': catalog.sequence, 'releases': len(catalog.releases),
            'packages': len(seen), 'bytes': total, 'catalog_and_apt_verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='checkout que contém catalogo/ e apt/')
    parser.add_argument('--config', type=Path, required=True, help='configuração pública obtida por canal confiável')
    parser.add_argument('--apt-keyring', type=Path, required=True, help='keyring público GPG confiável (.gpg)')
    args = parser.parse_args()
    result = verify_publication(args.root.resolve(), Config.load(args.config), args.apt_keyring)
    print(f'Publicação verificada: sequência {result["sequence"]}; {result["packages"]} pacote(s); catálogo e APT consistentes.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Verificação recusada: {exc}', file=sys.stderr)
        raise SystemExit(1)
