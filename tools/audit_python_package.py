#!/usr/bin/python3
"""Verifica o pacote Python Architecture: all sem instalar ou executar seu conteúdo."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile


def inspect_members(raw):
    files = 0
    native = []
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if member.isdir():
                continue
            files += 1
            prefix = archive.extractfile(member).read(8) if member.isfile() else b''
            if (prefix.startswith((b'\x7fELF', b'!<arch>\n', b'MZ', b'\x00asm'))
                    or re.search(r'\.so(?:\.|$)', member.name)
                    or member.name.endswith(('.a', '.o', '.dll', '.dylib', '.pyd', '.exe', '.whl'))):
                native.append(member.name)
    return files, native


def audit(package, expected_version):
    def command(*args):
        return subprocess.check_output(['dpkg-deb', *args, str(package)])
    # Campos separados: não depende da ordem de saída do control.
    version = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Version'], text=True).strip()
    architecture = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Architecture'], text=True).strip()
    if architecture != 'all' or version != expected_version:
        raise ValueError('Arquitetura/versão divergente do pacote Python esperado.')
    files = 0
    native = []
    for part, flag in (('payload', '--fsys-tarfile'), ('control', '--ctrl-tarfile')):
        count, found = inspect_members(command(flag))
        files += count
        native.extend(f'{part}:{name}' for name in found)
    if native:
        raise ValueError('Código nativo ou biblioteca incorporada em Architecture: all: ' + ', '.join(native))
    with package.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'package': package.name, 'version': version, 'architecture': architecture,
            'files_inspected': files, 'embedded_native_files': native, 'sha256': digest,
            'scope': 'Pacote próprio sem ELF/bibliotecas incorporadas. Não certifica as dependências nativas da distribuição nem execução em CPU v1.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--output', type=Path)
    opts = parser.parse_args()
    result = json.dumps(audit(opts.package, opts.expected_version), ensure_ascii=False, indent=2) + '\n'
    if opts.output:
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(result)
    print(result, end='')


if __name__ == '__main__':
    main()
