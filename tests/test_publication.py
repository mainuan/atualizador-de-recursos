import copy
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from publication import (PublicationError, encoded, inputs, load_previous, publish, select,
                         Redirects, validate_policy)
from publication_fixture import Fixture
from mainuan_recursos.catalog import Config, CatalogError, authenticate, parse_catalog
from mainuan_recursos.packages import build_plan, validate_effects, PlanningError
from mainuan_recursos.state import State
from helpers import package
from publication_verify import verify_publication


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixture = Fixture(Path(cls.temporary.name))

    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()
        cls.temporary.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.previous = self.root / 'empty'
        self.previous.mkdir()
        self.count = 0

    def run_publication(self, names='projeto-ficticio-1\n', message='Olá! Confira os programas:', github=None,
                        previous=None, policy=None, **kwargs):
        self.count += 1
        output = self.root / f'result-{self.count}'
        obj = publish(names.encode(), message.encode(), policy=policy or self.fixture.policy,
                      github=github or self.fixture.github(), previous_root=previous or self.previous,
                      output=output, private_key=kwargs.pop('private_key', self.fixture.private),
                      gpg_home=self.fixture.gpg_home, approval_commit='a' * 40,
                      approval_time=self.fixture.now, now=self.fixture.now, production=False, **kwargs)
        return output, obj

    def read_catalog(self, root):
        return json.loads((root / 'catalogo/novidades.json').read_bytes())

    def verify_tree(self, root):
        keyring = self.root / 'apt-publico.gpg'
        keyring.write_bytes(subprocess.check_output(['gpg', '--homedir', str(self.fixture.gpg_home),
                                                   '--batch', '--export', self.fixture.policy['apt_fingerprint']]))
        config = Config('https://github.com/mainuan/catalog', ('github.com',),
                        {'descartavel': self.fixture.policy['catalog_public_key']}, ('https://github.com/mainuan/',))
        return verify_publication(root, config, keyring, self.fixture.now)

    def test_joint_verification_of_catalog_ledger_apt_and_all_packages(self):
        root, _ = self.run_publication(names='\n'.join(self.fixture.programs))
        result = self.verify_tree(root)
        self.assertTrue(result['catalog_and_apt_verified'])
        self.assertEqual(result['packages'], 3)

    def test_joint_verifier_rejects_tampered_packages_indices_and_signatures(self):
        for relative in ('apt/Packages', 'apt/Packages.gz', 'apt/InRelease', 'apt/pool'):
            with self.subTest(relative=relative):
                root, _ = self.run_publication()
                path = root / relative
                if path.is_dir():
                    path = next(path.iterdir())
                data = path.read_bytes()
                path.write_bytes(data.replace(b'Origin: Mainuan', b'Origin: Alterado')
                                 if relative == 'apt/InRelease' else data + b'CORROMPIDO')
                with self.assertRaises(PublicationError):
                    self.verify_tree(root)

    def test_joint_verifier_rejects_valid_but_different_apt_edition(self):
        import shutil
        first, _ = self.run_publication()
        second, _ = self.run_publication(previous=first, github=self.fixture.github(2), refresh=True)
        shutil.rmtree(first / 'apt')
        shutil.copytree(second / 'apt', first / 'apt')
        with self.assertRaises(PublicationError):
            self.verify_tree(first)

    def test_joint_verifier_does_not_trust_unsigned_public_key_sources(self):
        root, _ = self.run_publication()
        keyring = self.root / 'sem-chave.gpg'
        keyring.write_bytes(b'')
        config = Config('https://github.com/mainuan/catalog', ('github.com',),
                        {'descartavel': self.fixture.policy['catalog_public_key']}, ('https://github.com/mainuan/',))
        with self.assertRaisesRegex(PublicationError, 'chave pública'):
            verify_publication(root, config, keyring, self.fixture.now)

    def test_one_approved_repository_real_control_names_versions_architectures(self):
        root, state = self.run_publication()
        feature = self.read_catalog(root)['releases'][0]['features'][0]
        self.assertEqual(feature['title'], 'Boas-vindas fictícias')
        self.assertEqual(feature['packages'][0]['name'], 'mainuan-dados-ficticios-1')
        self.assertEqual(feature['packages'][0]['min_version'], '1.0')
        self.assertEqual(feature['packages'][0]['architecture'], 'all')
        self.assertEqual(len(feature['packages'][0]['sha256']), 64)
        self.assertEqual(state['selected'][0]['source']['commit'], '1' * 40)
        self.assertEqual(state['selected'][0]['source']['release_id'], 11)
        self.assertEqual(state['selected'][0]['source']['assets'][0]['asset_id'], 101)

    def test_many_repositories_end_to_end_signature_and_apt_index(self):
        root, state = self.run_publication(names='\n'.join(self.fixture.programs))
        raw = (root / 'catalogo/novidades.json').read_bytes()
        config = Config('https://github.com/mainuan/catalog', ('github.com',),
                        {'descartavel': self.fixture.policy['catalog_public_key']}, ('https://github.com/mainuan/',))
        catalog = authenticate(raw, (root / 'catalogo/novidades.json.sig').read_bytes(), config, self.fixture.now)
        self.assertEqual(len(catalog.releases[0].packages), 3)
        self.assertEqual(len(state['pool']), 3)
        index = (root / 'apt/Packages').read_text()
        self.assertEqual(index.count('Package: '), 3)
        for p in catalog.releases[0].packages:
            self.assertIn('SHA256: ' + p.sha256, index)
        self.assertTrue((root / 'apt/InRelease').exists())
        self.assertIn('Acquire-By-Hash: yes', (root / 'apt/Release').read_text())

    def test_repository_does_not_exist_no_partial_output(self):
        with self.assertRaisesRegex(PublicationError, 'inexistente'):
            self.run_publication(names='projeto-ficticio-1\ninexistente')
        self.assertFalse((self.root / 'result-1').exists())

    def test_absent_debian_package(self):
        github = self.fixture.github()
        github.data['projeto-ficticio-1']['releases'][0]['assets'] = []
        with self.assertRaisesRegex(PublicationError, 'sem pacote Debian'):
            self.run_publication(github=github)

    def test_unapproved_draft_and_prerelease(self):
        for field in ('draft', 'prerelease'):
            github = self.fixture.github()
            github.data['projeto-ficticio-1']['releases'][0][field] = True
            with self.subTest(field=field), self.assertRaisesRegex(PublicationError, 'nenhuma release'):
                self.run_publication(github=github)

    def test_wrong_organization_private_archived(self):
        for field, value in (('full_name', 'evil/projeto-ficticio-1'), ('private', True),
                             ('archived', True), ('disabled', True)):
            github = self.fixture.github()
            github.data['projeto-ficticio-1']['repo'][field] = value
            with self.subTest(field=field), self.assertRaises(PublicationError):
                self.run_publication(github=github)

    def test_official_organization_can_publish_its_own_fork(self):
        github = self.fixture.github()
        github.data['projeto-ficticio-1']['repo']['fork'] = True
        _, state = self.run_publication(github=github)
        self.assertEqual(state['selected'][0]['source']['repository'], 'mainuan/projeto-ficticio-1')

    def test_message_only_preserves_exact_programs_without_github(self):
        first, one = self.run_publication()
        github = self.fixture.github(2)
        second, two = self.run_publication(previous=first, message='Nova mensagem\nSem trocar programas.', github=github)
        self.assertEqual(github.calls, [])
        self.assertEqual(one['selected'], two['selected'])
        self.assertEqual(len(self.read_catalog(second)['releases']), 2)
        self.assertEqual(self.read_catalog(second)['releases'][0]['summary'], 'Nova mensagem\nSem trocar programas.')

    def test_renewal_does_not_create_editorial_release(self):
        first, one = self.run_publication()
        second, two = self.run_publication(previous=first)
        self.assertEqual(two['sequence'], one['sequence'] + 1)
        self.assertEqual(self.read_catalog(first)['releases'], self.read_catalog(second)['releases'])

    def test_new_release_requires_new_approval(self):
        first, one = self.run_publication()
        second, two = self.run_publication(previous=first, github=self.fixture.github(2))
        self.assertEqual(one['selected'], two['selected'])
        third, three = self.run_publication(previous=second, github=self.fixture.github(2), refresh=True)
        self.assertEqual(three['selected'][0]['source']['assets'][0]['version'], '2.0')
        self.assertEqual(len(self.read_catalog(third)['releases']), 2)

    def test_packages_comment_is_explicit_new_approval(self):
        first, _ = self.run_publication()
        _, state = self.run_publication(previous=first, names='# Aprovar novamente\nprojeto-ficticio-1', github=self.fixture.github(2))
        self.assertEqual(state['selected'][0]['source']['assets'][0]['version'], '2.0')

    def test_old_versions_cannot_be_reused_even_after_repository_removed(self):
        first, _ = self.run_publication(github=self.fixture.github(2))
        second, _ = self.run_publication(previous=first, names='projeto-ficticio-2')
        with self.assertRaisesRegex(PublicationError, 'versão antiga'):
            self.run_publication(previous=second, github=self.fixture.github())

    def test_same_version_different_bytes_rejected(self):
        first, _ = self.run_publication()
        github = self.fixture.github(2)
        # Um .deb diferente com a MESMA versão Debian e SHA válido informado pelo GitHub.
        original = github.data['projeto-ficticio-1']['releases'][0]['assets'][0]
        modified = copy.deepcopy(original)
        modified['id'] = 999
        import shutil
        tree = self.root / 'modified-package'
        shutil.copytree(self.fixture.root / 'pkg-1-1', tree)
        (tree / 'usr/share/mainuan-dados-ficticios-1/info.txt').write_text('Outro conteúdo, mesma versão.\n')
        modified_deb = self.root / 'modified.deb'
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(tree), str(modified_deb)],
                       check=True, capture_output=True)
        raw = modified_deb.read_bytes()
        github.payloads = dict(github.payloads)
        github.payloads[999] = raw
        import hashlib
        modified.update(size=len(raw), digest='sha256:' + hashlib.sha256(raw).hexdigest())
        github.data['projeto-ficticio-1']['releases'][1]['assets'] = [modified]
        with self.assertRaisesRegex(PublicationError, 'bytes diferentes'):
            self.run_publication(previous=first, github=github, refresh=True)

    def test_missing_production_key_and_disabled_gate(self):
        with self.assertRaisesRegex(PublicationError, 'Chave privada ausente'):
            self.run_publication(private_key=None)
        policy = dict(self.fixture.policy, enabled=True, catalog_public_key='')
        with self.assertRaisesRegex(PublicationError, 'Chave pública'):
            validate_policy(policy, True)
        with self.assertRaisesRegex(PublicationError, 'desativada'):
            validate_policy(self.fixture.policy, True)

    def test_failed_catalog_signature_or_wrong_key_leaves_no_output(self):
        from publication import signature
        def broken(raw, key, key_id):
            return (signature(raw, key, key_id) if raw == b'preflight' else
                    encoded({'key_id': key_id, 'signature': 'AA=='}))
        with patch('publication.signature', side_effect=broken):
            with self.assertRaises(CatalogError):
                self.run_publication()
        self.assertFalse((self.root / 'result-1').exists())

    def test_failed_apt_signature_no_catalog_published(self):
        with patch('publication.create_apt', side_effect=PublicationError('Falha na assinatura APT')):
            with self.assertRaisesRegex(PublicationError, 'assinatura APT'):
                self.run_publication()
        self.assertFalse((self.root / 'result-1').exists())

    def test_real_gpg_failure_no_output(self):
        policy = dict(self.fixture.policy, apt_fingerprint='A' * 40)
        with self.assertRaisesRegex(PublicationError, 'assinatura APT'):
            self.run_publication(policy=policy)
        self.assertFalse((self.root / 'result-1').exists())

    def test_tampered_previous_publication_and_pool_fail(self):
        first, _ = self.run_publication()
        path = first / 'catalogo/publicacao.json'
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(PublicationError, 'Assinatura'):
            self.run_publication(previous=first)
        path.write_bytes(raw)
        next((first / 'apt/pool').iterdir()).write_bytes(b'tampered')
        with self.assertRaisesRegex(PublicationError, 'Integridade'):
            self.run_publication(previous=first)

    def test_absent_previous_state_requires_explicit_bootstrap(self):
        policy = dict(self.fixture.policy, bootstrap=False)
        with self.assertRaisesRegex(PublicationError, 'bootstrap'):
            self.run_publication(policy=policy)

    def test_asset_integrity_and_date_of_authorization(self):
        for field, value in (('digest', 'sha256:' + '0' * 64),
                             ('updated_at', (self.fixture.now + timedelta(hours=1)).isoformat())):
            github = self.fixture.github()
            github.data['projeto-ficticio-1']['releases'][0]['assets'][0][field] = value
            with self.subTest(field=field), self.assertRaises(PublicationError):
                self.run_publication(github=github)

    def test_future_release_never_silently_selected(self):
        github = self.fixture.github(2)
        github.data['projeto-ficticio-1']['releases'][1]['published_at'] = (self.fixture.now + timedelta(hours=1)).isoformat()
        _, state = self.run_publication(github=github)
        self.assertEqual(state['selected'][0]['source']['release_id'], 11)

    def test_inputs_reject_urls_options_duplicates_controls(self):
        for value in ('https://github.com/mainuan/a', '../evil', '--option\n--option',
                      'mainuan/a', 'a\na', 'Repo\nrepo', '\n', 'repo;id'):
            with self.subTest(value=value), self.assertRaises((PublicationError, CatalogError)):
                inputs(value.encode(), 'Olá'.encode())
        with self.assertRaises(CatalogError):
            inputs(b'valid-repo', b'hello\x1b')

    def test_unsafe_asset_redirect(self):
        for url in ('http://github.com/mainuan/a', 'https://evil.example/a',
                    'https://user@github.com/a', 'https://github.com:444/a'):
            with self.subTest(url=url), self.assertRaises(PublicationError):
                Redirects().redirect_request(None, None, 302, '', {}, url)

    def test_article_optional_fallback_and_multiline_plaintext(self):
        root, _ = self.run_publication(message='Olá!\n<b>Texto simples</b>')
        obj = self.read_catalog(root)
        obj['releases'][0].pop('article_url')
        release = parse_catalog(encoded(obj), ('github.com',), self.fixture.now,
                                ('https://github.com/mainuan/',)).releases[0]
        self.assertEqual(release.article_url, 'https://github.com/mainuan/projeto-ficticio-1/releases')
        self.assertIn('\n<b>', release.summary)

    def test_pinned_apt_version_hash_and_already_received(self):
        root, _ = self.run_publication()
        release = parse_catalog((root / 'catalogo/novidades.json').read_bytes(), ('github.com',), self.fixture.now).releases[0]
        name = release.packages[0].name
        pkg = package(candidate='1.0', arch='all')
        pkg.candidate.sha256 = release.packages[0].sha256
        self.assertEqual(build_plan(release, {name: pkg}).rows[0].status, 'Instalar')
        pkg.candidate.sha256 = '0' * 64
        self.assertTrue(build_plan(release, {name: pkg}).blockers)
        for installed in ('1.0', '2.0'):
            pkg = package(installed=installed, candidate='9.0', arch='all')
            plan = build_plan(release, {name: pkg})
            self.assertTrue(plan.complete)
            self.assertFalse(plan.pending)
            state = State()
            state.viewed(release)
            self.assertNotEqual(state.entry(release)['packages'], 'installed')
            state.observe(release, plan)
            self.assertEqual(state.entry(release)['packages'], 'installed')

    def test_apt_newer_candidate_does_not_replace_exact_approval(self):
        root, _ = self.run_publication()
        release = parse_catalog((root / 'catalogo/novidades.json').read_bytes(), ('github.com',), self.fixture.now).releases[0]
        p = release.packages[0]
        pkg = package(candidate='9.0', arch='all')
        from helpers import version
        approved = version('1.0', arch='all')
        approved.sha256 = p.sha256
        pkg.versions.append(approved)
        plan = build_plan(release, {p.name: pkg})
        self.assertTrue(plan.blockers)
        self.assertFalse(plan.pending)
        # Mesmo com a versão aprovada disponível, não contornar a escolha/pinning APT.
        pkg.candidate = approved
        plan = build_plan(release, {p.name: pkg})
        self.assertEqual(plan.pending[0].identity, (p.name, '1.0', 'all'))
        effects = [(12, f'{p.name};1.0;all;mainuan')]
        validate_effects(effects, [plan.rows[0].identity], {p.name: pkg},
                         pins={plan.rows[0].identity: p.sha256})
        approved.sha256 = '0' * 64
        with self.assertRaisesRegex(PlanningError, 'integridade'):
            validate_effects(effects, [plan.rows[0].identity], {p.name: pkg},
                             pins={plan.rows[0].identity: p.sha256})

    def test_planned_key_rotation_preserves_sequence(self):
        first, one = self.run_publication()
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        import base64
        key = Ed25519PrivateKey.generate()
        policy = dict(self.fixture.policy, catalog_key_id='nova-chave',
                      catalog_public_key=base64.b64encode(key.public_key().public_bytes(
                          serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode(),
                      previous_catalog_keys={'descartavel': self.fixture.policy['catalog_public_key']})
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
        second, two = self.run_publication(previous=first, policy=policy, private_key=private)
        self.assertGreater(two['sequence'], one['sequence'])
        self.assertEqual(json.loads((second / 'catalogo/novidades.json.sig').read_bytes())['key_id'], 'nova-chave')

    def test_signed_generated_catalog_preserves_native_ui_and_optional_article(self):
        from qt_support import APP, wait_until
        from mainuan_recursos.demo import Demo
        from mainuan_recursos.gui import Window
        from PyQt6.QtWidgets import QLabel
        root, _ = self.run_publication(names='\n'.join(self.fixture.programs),
                                       message='Olá! O Mainuan tem novidades.\nConfira quais são:')
        obj = self.read_catalog(root)
        obj['releases'][0].pop('article_url')
        demo = Demo()
        demo.catalog = parse_catalog(encoded(obj), ('github.com',), self.fixture.now, ('https://github.com/mainuan/',))
        state = State()
        window = Window(state, demo=demo)
        try:
            window.reload()
            wait_until(lambda: window.worker is None)
            self.assertEqual(len(window.program_labels), 3)
            self.assertEqual(demo.plan(window.current).rows[0].architecture, 'all')
            self.assertEqual(window.program_labels[0].text(), '•  Boas-vindas fictícias')
            self.assertEqual(window.summary.text(), obj['releases'][0]['summary'])
            self.assertEqual(sum(label.text() == window.current.summary
                                 for label in window.findChildren(QLabel)), 1)
            with patch('mainuan_recursos.gui.QDesktopServices.openUrl', return_value=True) as opened:
                window.know.click()
                self.assertEqual(opened.call_args[0][0].toString(), 'https://github.com/mainuan/projeto-ficticio-1/releases')
            self.assertEqual(state.entry(window.current)['presentation'], 'viewed')
            self.assertNotEqual(state.entry(window.current)['packages'], 'installed')
        finally:
            window.close()
            window.deleteLater()
            APP.processEvents()


if __name__ == '__main__':
    unittest.main()
