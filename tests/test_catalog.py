import base64
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mainuan_recursos.catalog import (CatalogError, Config, OfficialRedirects, authenticate, decode,
                                     download, https_url, parse_catalog)
from mainuan_recursos.repository import Repository
from mainuan_recursos.state import State
from helpers import HOSTS, NOW, catalog_dict


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.obj = catalog_dict()
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.config = Config('https://mainuan.example/catalog.json', HOSTS, {'test': base64.b64encode(public).decode()})

    def raw(self):
        return json.dumps(self.obj).encode()

    def sign(self, raw):
        return json.dumps({'key_id': 'test', 'signature': base64.b64encode(self.key.sign(raw)).decode()}).encode()

    def test_signed_catalog(self):
        raw = self.raw()
        result = authenticate(raw, self.sign(raw), self.config, NOW)
        self.assertEqual(result.releases[0].packages[0].name, 'mainuan-boas-vindas')

    def test_tampering(self):
        raw = self.raw()
        with self.assertRaises(CatalogError):
            authenticate(raw + b' ', self.sign(raw), self.config, NOW)

    def test_unknown_key(self):
        raw = self.raw()
        with self.assertRaises(CatalogError):
            authenticate(raw, self.sign(raw).replace(b'test', b'evil'), self.config, NOW)

    def test_wrong_private_key(self):
        raw = self.raw()
        self.key = Ed25519PrivateKey.generate()
        with self.assertRaises(CatalogError):
            authenticate(raw, self.sign(raw), self.config, NOW)

    def test_invalid_signature_encoding(self):
        with self.assertRaises(CatalogError):
            authenticate(self.raw(), b'{"key_id":"test","signature":"!"}', self.config, NOW)

    def test_expired_future_and_long_validity(self):
        for field, value in (('expires_at', '2026-10-21T00:00:00Z'), ('published_at', '2026-10-23T00:00:00Z'),
                             ('expires_at', '2027-10-22T00:00:00Z')):
            with self.subTest(field=field, value=value):
                obj = catalog_dict()
                obj[field] = value
                with self.assertRaises(CatalogError):
                    parse_catalog(json.dumps(obj).encode(), HOSTS, NOW)

    def test_unknown_fields_including_commands_rejected(self):
        for obj in (self.obj, self.obj['releases'][0], self.obj['releases'][0]['features'][0]['packages'][0]):
            obj['command'] = 'id'
            with self.assertRaises(CatalogError):
                parse_catalog(self.raw(), HOSTS, NOW)
            del obj['command']

    def test_package_names_and_versions_are_literals(self):
        pkg = self.obj['releases'][0]['features'][0]['packages'][0]
        for name in ('apt;id', '--option', '$(id)', '/tmp/local.deb', 'foo*', 'foo:amd64', 'a'):
            with self.subTest(name=name):
                pkg['name'] = name
                with self.assertRaises(CatalogError):
                    parse_catalog(self.raw(), HOSTS, NOW)
        pkg['name'] = 'mainuan-teste'
        for value in ('--option', '1;id', '', '1 2', '1.0-', '1:' + '1' * 130):
            pkg['min_version'] = value
            with self.assertRaises(CatalogError):
                parse_catalog(self.raw(), HOSTS, NOW)

    def test_duplicate_keys_release_packages_and_controls(self):
        with self.assertRaises(CatalogError):
            decode(b'{"sequence":1,"sequence":2}')
        self.obj['releases'].append(self.obj['releases'][0])
        with self.assertRaises(CatalogError):
            parse_catalog(self.raw(), HOSTS, NOW)
        self.obj = catalog_dict()
        self.obj['releases'][0]['features'].append(self.obj['releases'][0]['features'][0])
        with self.assertRaises(CatalogError):
            parse_catalog(self.raw(), HOSTS, NOW)
        self.obj = catalog_dict()
        self.obj['releases'][0]['title'] = 'Olá\x1b'
        with self.assertRaises(CatalogError):
            parse_catalog(self.raw(), HOSTS, NOW)

    def test_types_and_limits(self):
        for key, value in (('sequence', True), ('sequence', -1), ('releases', {}), ('schema_version', 2)):
            obj = catalog_dict()
            obj[key] = value
            with self.assertRaises(CatalogError):
                parse_catalog(json.dumps(obj).encode(), HOSTS, NOW)
        for raw in (b'x' * (1024 * 1024 + 1), b'{', b'{"x":NaN}'):
            with self.assertRaises(CatalogError):
                decode(raw)

    def test_url_restrictions(self):
        for url in ('http://mainuan.example/a', 'file:///tmp/a', 'https://evil.example/a',
                    'https://mainuan.example.evil/a', 'https://user@mainuan.example/a',
                    'https://mainuan.example:444/a', 'https://mainuan.example/a#fragment'):
            with self.subTest(url=url), self.assertRaises(CatalogError):
                https_url(url, HOSTS)
        self.assertEqual(https_url('https://mainuan.example/a?b=1', HOSTS), 'https://mainuan.example/a?b=1')

    def test_unsafe_redirect_fails_before_request(self):
        with self.assertRaises(CatalogError):
            OfficialRedirects(HOSTS).redirect_request(None, None, 302, '', {}, 'http://evil.example/')

    def test_compatibility(self):
        release = parse_catalog(self.raw(), HOSTS, NOW).releases[0]
        self.assertTrue(release.compatible({'distro_id':'mainuan','version_id':'26.04','architecture':'amd64'}))
        self.assertFalse(release.compatible({'distro_id':'ubuntu','version_id':'26.04','architecture':'amd64'}))

    def test_empty_production_configuration_fails_closed(self):
        path = Path(__file__).resolve().parents[1] / 'data/atualizador-recursos.json'
        with self.assertRaises(CatalogError):
            Config.load(path)

    def test_valid_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            path.write_text(json.dumps(self.config.__dict__))
            self.assertEqual(Config.load(path), self.config)

    def test_cache_is_authenticated_again_and_offline(self):
        raw = self.raw()
        with tempfile.TemporaryDirectory() as temp:
            repository = Repository(self.config, Path(temp))
            with patch('mainuan_recursos.catalog.datetime') as clock, patch('mainuan_recursos.repository.fetch', return_value=(raw,self.sign(raw))):
                clock.now.return_value = NOW
                clock.fromisoformat.side_effect = __import__('datetime').datetime.fromisoformat
                catalog, online = repository.load()
                self.assertTrue(online)
            with patch('mainuan_recursos.repository.fetch', side_effect=OSError('offline')), patch('mainuan_recursos.catalog.datetime') as clock:
                clock.now.return_value = NOW
                clock.fromisoformat.side_effect = __import__('datetime').datetime.fromisoformat
                cached, online = repository.load()
                self.assertFalse(online)
                self.assertEqual(cached, catalog)
                repository.cache.write_text('{"catalog":"!", "signature":"!"}')
                with self.assertRaises(Exception):
                    repository.load()

    def test_bad_signature_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Repository(self.config, Path(temp))
            with patch('mainuan_recursos.repository.fetch', return_value=(self.raw(), b'{}')):
                with self.assertRaises(CatalogError):
                    repo.load()

    def test_github_organization_path_is_required(self):
        from mainuan_recursos.catalog import scoped_url
        prefixes = ('https://github.com/mainuan/',)
        for url in ('https://github.com/outra-conta/repo', 'https://github.com/mainuan-falso/repo',
                    'https://github.com/mainuan/../evil', 'https://github.com/mainuan/%2e%2e/evil',
                    'https://github.com/mainuan/%252e%252e/evil', 'https://github.com/mainuan//evil',
                    'https://github.com/mainuan/%2f/evil', 'https://raw.githubusercontent.com/mainuan/repo/main/a'):
            with self.subTest(url=url), self.assertRaises(CatalogError):
                scoped_url(url, prefixes)
        for url in ('https://github.com/mainuan/atualizadorderecursos/releases/tag/v1.0',
                    'https://github.com/mainuan/atualizadorderecursos'):
            self.assertEqual(scoped_url(url, prefixes), url)

    def test_production_url_configured_but_no_key_provisioned(self):
        obj = json.loads((Path(__file__).resolve().parents[1] / 'data/atualizador-recursos.json').read_text())
        self.assertEqual(obj['manifest_url'], 'https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json')
        self.assertEqual(obj['article_prefixes'], ['https://github.com/mainuan/'])
        self.assertEqual(obj['keys'], {})

    def test_signed_but_unofficial_article_path_is_rejected(self):
        self.obj['releases'][0]['article_url'] = 'https://github.com/evil/repo'
        raw = self.raw()
        config = Config(self.config.manifest_url, ('github.com',), self.config.keys, ('https://github.com/mainuan/',))
        with self.assertRaises(CatalogError):
            authenticate(raw, self.sign(raw), config, NOW)

    def test_replayed_catalog_cannot_replace_cache(self):
        raw = self.raw()
        with tempfile.TemporaryDirectory() as temp:
            repository = Repository(self.config, Path(temp), watermark=(2, 'newer'))
            repository.cache.write_bytes(b'preservar')
            with patch('mainuan_recursos.catalog.datetime') as clock, patch('mainuan_recursos.repository.fetch', return_value=(raw,self.sign(raw))):
                clock.now.return_value = NOW
                clock.fromisoformat.side_effect = __import__('datetime').datetime.fromisoformat
                with self.assertRaises(CatalogError):
                    repository.load()
            self.assertEqual(repository.cache.read_bytes(),b'preservar')
