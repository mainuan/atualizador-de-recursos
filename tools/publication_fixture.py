"""Repositórios e Debian fictícios, sem rede e sem instalação. Somente homologação."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from publication import PublicationError


class Fixture:
    def __init__(self, root):
        self.root = root
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.gpg_home = root / 'gnupg-descartavel'
        self.gpg_home.mkdir(mode=0o700)
        gpg = ['gpg', '--homedir', str(self.gpg_home), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '']
        subprocess.run(gpg + ['--quick-generate-key', 'TESTE DESCARTAVEL <teste@example.invalid>',
                              'ed25519', 'sign', '2d'], check=True, capture_output=True)
        fingerprint = next(line.split(':')[9] for line in subprocess.check_output(
            gpg + ['--with-colons', '--list-keys'], text=True, stderr=subprocess.DEVNULL).splitlines() if line.startswith('fpr:'))
        self.key = Ed25519PrivateKey.generate()
        self.private = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption())
        public = base64.b64encode(self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        self.policy = {'enabled': False, 'bootstrap': True, 'organization': 'mainuan',
                       'architectures': ['amd64'], 'distribution_ids': ['mainuan', 'ubuntu'],
                       'distribution_versions': ['2026', '26.04'], 'catalog_key_id': 'descartavel',
                       'catalog_public_key': public, 'apt_fingerprint': fingerprint, 'article_url': ''}
        self.programs = {}
        self.payloads = {}
        for index, friendly in enumerate(('Boas-vindas fictícias', 'Aparência fictícia', 'Ajuda fictícia'), 1):
            name = f'projeto-ficticio-{index}'
            package = f'mainuan-dados-ficticios-{index}'
            releases = []
            for stage in (1, 2):
                tree = root / f'pkg-{index}-{stage}'
                (tree / 'DEBIAN').mkdir(parents=True)
                (tree / 'DEBIAN/control').write_text(
                    f'Package: {package}\nVersion: {stage}.0\nArchitecture: all\nSection: misc\nPriority: optional\n'
                    f'Maintainer: Teste <teste@example.invalid>\nDescription: {friendly}\n Somente dados de teste.\n')
                data = tree / f'usr/share/{package}/info.txt'
                data.parent.mkdir(parents=True)
                data.write_text('Pacote fictício contendo somente este texto.\n')
                path = root / f'fixture-{index}-{stage}.deb'
                subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(tree), str(path)],
                               check=True, capture_output=True)
                raw = path.read_bytes()
                asset_id = index * 100 + stage
                self.payloads[asset_id] = raw
                date = (self.now - timedelta(days=3-stage)).isoformat()
                asset = {'id': asset_id, 'name': f'{package}_{stage}.0_all.deb', 'size': len(raw),
                         'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'state': 'uploaded',
                         'created_at': date, 'updated_at': date,
                         'browser_download_url': f'https://github.com/mainuan/{name}/releases/download/v{stage}/arquivo.deb'}
                releases.append({'id': index * 10 + stage, 'name': friendly, 'tag_name': f'v{stage}',
                                 'draft': False, 'prerelease': False, 'published_at': date, 'updated_at': date,
                                 'html_url': f'https://github.com/mainuan/{name}/releases/tag/v{stage}', 'assets': [asset]})
            self.programs[name] = {'repo': {'id': index, 'full_name': 'mainuan/' + name,
                                          'owner': {'login': 'mainuan', 'type': 'Organization'},
                                          'private': False, 'archived': False, 'fork': False}, 'releases': releases}

    def github(self, stage=1):
        data = copy.deepcopy(self.programs)
        for obj in data.values():
            obj['releases'] = obj['releases'][:stage]
        return FakeGitHub(data, self.payloads)

    def close(self):
        subprocess.run(['gpgconf', '--homedir', str(self.gpg_home), '--kill', 'all'], capture_output=True)


class FakeGitHub:
    def __init__(self, data, payloads):
        self.data, self.payloads, self.calls = data, payloads, []

    def repository(self, name):
        self.calls.append(name)
        if name not in self.data:
            raise PublicationError(f'{name}: repositório inexistente (fictício).')
        return self.data[name]['repo']

    def releases(self, name):
        return self.data[name]['releases']

    def commit(self, name, tag):
        return ('1' if tag == 'v1' else '2') * 40

    def assets(self, name, release_id):
        return next(r['assets'] for r in self.data[name]['releases'] if r['id'] == release_id)

    def download(self, name, asset):
        return self.payloads[asset['id']]
