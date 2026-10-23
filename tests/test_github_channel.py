"""Fluxo distribuído: entrada normal, GitHub, cache e instalação sem tocar no host."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from helpers import package
from mainuan_recursos import github_channel as github
from mainuan_recursos.catalog import CatalogError
from mainuan_recursos.gui import Window
from mainuan_recursos.packagekit import Result
from mainuan_recursos.session import SessionKind
from mainuan_recursos.state import State
from qt_support import APP, wait_until

SYSTEM = {'distro_id': 'mainuan', 'version_id': '26.04', 'architecture': 'amd64'}


class Fixture:
    def __init__(self, names=('programa-um',), version='1.0'):
        self.names, self.version = names, version
        self.message = 'Olá! O Mainuan tem novidades.\n\nConfira quais são:\n'
        self.commit = 'a' * 40
        self.payload = b'pacote ficticio, nunca instalado'
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.overrides = {}
        self.calls = []

    def asset(self, name):
        filename = f'pacote-{name}_{self.version}_all.deb'
        return {'id': 123, 'name': filename, 'state': 'uploaded', 'size': len(self.payload),
                'digest': 'sha256:' + self.digest,
                'browser_download_url': f'https://github.com/mainuan/{name}/releases/download/v{self.version}/{filename}'}

    def metadata(self, url, limit=1024*1024):
        self.calls.append(url)
        if url in self.overrides:
            value = self.overrides[url]
            if isinstance(value, Exception):
                raise value
            return value
        if url == github.API + github.OFFICIAL + '/commits/main':
            value = {'sha': self.commit}
        elif url.endswith('/packages.txt'):
            return ('\n'.join(self.names) + '\n').encode()
        elif url.endswith('/message.txt'):
            return self.message.encode()
        else:
            name, _, suffix = url.removeprefix(github.API).partition('/')
            if not suffix:
                value = {'id': 111, 'full_name': 'mainuan/' + name, 'owner': {'login': 'mainuan'}}
            elif suffix.startswith('commits/'):
                value = {'sha': 'b' * 40}
            elif suffix.startswith('releases?') or suffix == 'releases/222':
                release = {'id': 222, 'tag_name': 'v' + self.version, 'name': 'Programa amigável ' + name,
                          'published_at': '2026-01-01T00:00:00Z', 'draft': False, 'prerelease': False,
                          'html_url': f'https://github.com/mainuan/{name}/releases/tag/v{self.version}'}
                value = release if suffix == 'releases/222' else [release]
            elif suffix.startswith('releases/222/assets?'):
                value = [self.asset(name)]
            elif suffix == 'releases/assets/123':
                value = self.asset(name)
            else:
                raise AssertionError('Consulta não esperada: ' + url)
        return json.dumps(value).encode()


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.state = State(self.directory / 'state.json')
        self.fixture = Fixture()
        self.channel = github.GitHubChannel(self.directory, self.state)
        for target, value in [('system_identity', SYSTEM), ('session_kind', SessionKind.INSTALLED)]:
            p = patch.object(github, target, return_value=value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(github, 'metadata', side_effect=self.fixture.metadata)
        p.start(); self.addCleanup(p.stop)

    def load(self):
        return self.channel.load()[0].releases[0]

    def test_metadata_only_consistent_commit_and_real_package_name(self):
        release = self.load()
        self.assertEqual(release.summary, self.fixture.message)
        self.assertEqual(release.packages[0].name, 'pacote-programa-um')
        self.assertEqual(release.features[0].title, 'Programa amigável programa-um')
        self.assertTrue(all('/'+self.fixture.commit+'/' in url for url in self.fixture.calls if url.endswith('.txt')))
        self.assertFalse((self.directory/'pacotes-github').exists())
        self.assertFalse(any('/releases/download/' in url for url in self.fixture.calls))

    def test_multiple_programs_and_architecture_selection(self):
        self.fixture.names = ('programa-um', 'programa-dois')
        release = self.load()
        self.assertEqual(len(release.features), 2)
        self.assertEqual(len(release.packages), 2)
        incompatible = self.fixture.asset('programa-um')
        incompatible['name'] = incompatible['name'].replace('_all.deb', '_arm64.deb')
        self.fixture.overrides[github.API+'programa-um/releases/222/assets?per_page=100&page=1'] = json.dumps([incompatible]).encode()
        with self.assertRaisesRegex(CatalogError, 'compatível'):
            self.load()

    def test_new_release_without_source_or_editorial_change(self):
        old = self.load()
        self.fixture.version = '2.0'
        new = self.load()
        self.assertNotEqual(new.key, old.key)
        self.assertEqual(new.packages[0].min_version, '2.0')
        self.assertIn(old, self.channel.catalog.releases)
        self.assertEqual(self.state.data['sequence'], 2)

    def test_message_change_and_unrelated_main_commit(self):
        first = self.load()
        self.state.viewed(first)
        self.fixture.commit = 'c'*40
        self.assertEqual(self.load(), first)
        self.assertEqual(self.state.data['sequence'], 1)
        self.fixture.message += '\nMais novidades!'
        new = self.load()
        self.assertNotEqual(new.key, first.key)
        self.assertTrue(self.state.due(new))
        self.assertFalse(self.state.due(first))

    def test_missing_digest_unofficial_repo_and_prerelease_are_blocked(self):
        url = github.API+'programa-um/releases/222/assets?per_page=100&page=1'
        asset = self.fixture.asset('programa-um'); asset.pop('digest')
        self.fixture.overrides[url] = json.dumps([asset]).encode()
        with self.assertRaisesRegex(CatalogError, 'SHA-256'):
            self.load()
        self.fixture.overrides.clear()
        self.fixture.overrides[github.API+'programa-um'] = json.dumps({'id':111, 'full_name':'invasor/programa-um'}).encode()
        with self.assertRaisesRegex(CatalogError, 'oficial'):
            self.load()
        self.fixture.overrides.clear()
        release = {'id':222,'published_at':'2026-01-01T00:00:00Z','prerelease':True}
        self.fixture.overrides[github.API+'programa-um/releases?per_page=100&page=1'] = json.dumps([release]).encode()
        with self.assertRaisesRegex(CatalogError, 'estável'):
            self.load()

    def test_replacement_and_rollback_preserve_last_valid_cache(self):
        self.load()
        valid = self.channel.cache_path.read_bytes()
        self.fixture.digest = 'c'*64
        with self.assertRaisesRegex(CatalogError, 'substituído'):
            self.load()
        self.assertEqual(self.channel.cache_path.read_bytes(), valid)
        self.fixture.digest = hashlib.sha256(self.fixture.payload).hexdigest()
        self.fixture.version = '0.9'
        with self.assertRaisesRegex(CatalogError, 'Retrocesso'):
            self.load()

    def test_withdrawn_release_or_retargeted_tag_cannot_be_installed(self):
        release = self.load()
        asset = self.channel._assets(release)[0]
        self.channel._refresh_asset(asset)
        self.fixture.overrides[github.API+'programa-um/releases/222'] = json.dumps({'id':222,'draft':True}).encode()
        with self.assertRaisesRegex(CatalogError,'retirada'):
            self.channel._refresh_asset(asset)
        self.fixture.overrides.clear()
        self.fixture.overrides[github.API+'programa-um/commits/v1.0'] = json.dumps({'sha':'d'*40}).encode()
        with self.assertRaisesRegex(CatalogError,'substituída'):
            self.channel._refresh_asset(asset)

    def test_offline_history_survives_restart_but_never_allows_install(self):
        release = self.load()
        self.state.postpone(release, now=1000)
        channel = github.GitHubChannel(self.directory, State(self.state.path))
        with patch.object(github, 'metadata', side_effect=OSError('Sem conexão')):
            catalog, online = channel.load()
        self.assertFalse(online)
        self.assertEqual(catalog.releases[0], release)
        self.assertFalse(channel.state.due(release, now=87399))
        self.assertTrue(channel.state.due(release, now=87400))
        with self.assertRaisesRegex(CatalogError, 'online'):
            channel.prepare_plan(release, Mock())

    def test_installed_version_is_received_without_download_or_dependency_read(self):
        release = self.load()
        for version in ('1.0', '2.0'):
            with patch('apt.Cache', return_value={'pacote-programa-um':package(installed=version)}), \
                 patch.object(self.channel, '_download') as download, patch.object(self.channel, 'verify_file') as verify:
                self.assertTrue(self.channel.prepare_plan(release, Mock()).complete)
                download.assert_not_called(); verify.assert_not_called()

    def test_download_only_after_install_and_internal_metadata_verified(self):
        release = self.load()
        asset = self.channel._assets(release)[0]
        deb = {'Package':asset['name'], 'Version':'1.0', 'Architecture':'all'}
        fake_deb = Mock(); fake_deb.__getitem__ = Mock(side_effect=deb.__getitem__)
        fake_deb.check.return_value = True; fake_deb.required_changes = ([], [], [])
        with patch('apt.Cache', return_value={}), patch.object(github, 'supports_local_files'), \
             patch.object(github.os, 'geteuid', return_value=1000), \
             patch.object(github, 'open_url', return_value=io.BytesIO(self.fixture.payload)) as fetch, \
             patch('apt.debfile.DebPackage', return_value=fake_deb):
            self.assertTrue(self.channel.prepare_plan(release, Mock()).pending)
            fetch.assert_called_once_with(asset['url'], asset['repository'])
            self.channel.verify_file(asset)
            deb['Package'] = 'outro-pacote'
            with self.assertRaisesRegex(CatalogError, 'Metadados'):
                self.channel.verify_file(asset)

    def test_corrupt_download_is_deleted_and_never_prepared(self):
        release = self.load()
        asset = self.channel._assets(release)[0]
        with patch.object(github, 'open_url', return_value=io.BytesIO(b'corrompido')):
            with self.assertRaisesRegex(CatalogError, 'integridade'):
                self.channel._download(asset, Mock())
        self.assertFalse(self.channel.path(asset).exists())
        self.assertFalse(list(self.directory.rglob('.download-*')))

    def test_additional_packages_removal_or_missing_effect_are_blocked(self):
        release = self.load()
        with patch('apt.Cache', return_value={}):
            plan = self.channel.plan(release)
        normal = ((12, 'pacote-programa-um;1.0;all;local'),)
        with patch.object(self.channel, 'verify_file'):
            self.assertEqual(len(self.channel.validate_simulation(release, plan, normal)), 1)
            for effects in ((), normal + ((12,'dependencia;1.0;all;local'),), ((13, normal[0][1]),)):
                with self.assertRaises(CatalogError):
                    self.channel.validate_simulation(release, plan, effects)

    def test_normal_window_uses_channel_and_one_click_revalidates_twice(self):
        received = {}
        def cache():
            return {name:package(installed=version, arch='all') for name,version in received.items()}
        calls = []
        class FakeTransaction(QObject):
            progress = pyqtSignal(str, object)
            finished = pyqtSignal(object)
            def start(tx, method, paths, simulate=False, authorized=False):
                calls.append((method, simulate, authorized))
                assert method == 'InstallFiles'
                if not simulate:
                    assert authorized
                    received['pacote-programa-um'] = '1.0'
                QTimer.singleShot(0, lambda:tx.finished.emit(Result(True, ((12,'pacote-programa-um;1.0;all;local'),))))
        window = Window(self.state, self.directory, github_channel=self.channel)
        self.addCleanup(window.deleteLater)
        window.controller.transaction_factory = FakeTransaction
        window.show()
        with patch('apt.Cache', side_effect=cache), patch('mainuan_recursos.gui.system_identity', return_value=SYSTEM), \
             patch.object(self.channel, '_download'), patch.object(self.channel, '_refresh_asset'), \
             patch.object(self.channel, 'verify_file'), patch.object(github, 'supports_local_files'), \
             patch.object(github.os, 'geteuid', return_value=1000), \
             patch('apt.debfile.DebPackage') as deb:
            deb.return_value.check.return_value = True; deb.return_value.required_changes = ([], [], [])
            window.reload(); wait_until(lambda:window.worker is None)
            self.assertIsNone(window.github_trial)
            self.assertTrue(window.install.isEnabled())
            self.assertNotIn('Homologação', window.windowTitle())
            self.assertEqual(calls, [])
            window.install.click()
            wait_until(lambda:not window.controller.busy and bool(calls))
            self.assertEqual(calls, [('InstallFiles', True, False), ('InstallFiles', True, True), ('InstallFiles', False, True)])
            self.assertIn('Concluído!', window.status.text())
            self.assertEqual(self.state.entry(window.current)['packages'], 'installed')
            self.assertFalse(window.install.isEnabled())
        window.close()

    def test_initial_query_without_network_has_clear_error(self):
        with patch.object(github, 'metadata', side_effect=OSError('Sem conexão')):
            with self.assertRaisesRegex(OSError, 'Sem conexão'):
                self.channel.load()

    def test_real_debian_control_matches_asset_and_rejects_misleading_filename(self):
        staging = self.directory/'staging'
        (staging/'DEBIAN').mkdir(parents=True)
        control = staging/'DEBIAN/control'
        control.write_text('Package: pacote-programa-um\nVersion: 1.0\nArchitecture: all\nMaintainer: Mainuan <teste@example.org>\nDescription: pacote ficticio de dados\n')
        deb = self.directory/'ficticio.deb'
        subprocess.run(['dpkg-deb','--build','--root-owner-group',str(staging),str(deb)],check=True,capture_output=True)
        self.fixture.payload = deb.read_bytes()
        self.fixture.digest = hashlib.sha256(self.fixture.payload).hexdigest()
        release = self.load()
        asset = self.channel._assets(release)[0]
        with patch.object(github,'open_url',return_value=io.BytesIO(self.fixture.payload)):
            self.channel._download(asset, Mock())
        self.channel.verify_file(asset)
        # Assinatura de checksum não substitui a conferência do control interno.
        altered = {**asset,'version':'9.0'}
        with self.assertRaisesRegex(CatalogError,'Metadados'):
            self.channel.verify_file(altered)

    def test_second_simulation_and_authorization_failure_never_report_success(self):
        release = self.load()
        with patch('apt.Cache', return_value={}):
            plan = self.channel.plan(release)
        for scenario in ('cancelled', 'changed', 'unverified'):
            calls=[]
            channel=self.channel
            class FakeTransaction(QObject):
                progress=pyqtSignal(str,object)
                finished=pyqtSignal(object)
                def start(tx,method,values,simulate=False,authorized=False):
                    calls.append((simulate,authorized))
                    effect=((12,'pacote-programa-um;1.0;all;local'),)
                    if scenario=='changed' and len(calls)==2:
                        effect+=((12,'outro;1.0;all;local'),)
                    result=Result(False,error='Autorização cancelada') if not simulate and scenario=='cancelled' else Result(True,effect)
                    QTimer.singleShot(0,lambda:tx.finished.emit(result))
            controller=github.GitHubController(channel)
            self.addCleanup(controller.deleteLater)
            controller.transaction_factory=FakeTransaction
            controller.plan_provider=lambda _:plan
            channel.paths=('/tmp/ficticio.deb',)
            completed=[]
            controller.completed.connect(lambda *args:completed.append(args))
            controller.prepared.connect(controller.confirm)
            with patch.object(channel,'verify_file'), patch.object(channel,'plan',return_value=plan):
                controller.prepare(release)
                wait_until(lambda:bool(completed))
            self.assertFalse(completed[0][0])
            self.assertNotIn('Concluído!',completed[0][1])
            if scenario=='changed':
                self.assertFalse(any(not simulate for simulate,_ in calls))


class OriginTests(unittest.TestCase):
    def test_https_scope_and_redirect_validation(self):
        for url in ('http://api.github.com/repos/mainuan/repo', 'https://api.github.com/repos/mainuan-malicioso/repo',
                    'https://github.com/terceiro/repo/releases/download/v1/pkg.deb',
                    'https://github.com/mainuan/repo/releases/download/../v1/pkg.deb',
                    'https://github.com/mainuan/repo/releases/download/%2e%2e/v1/pkg.deb'):
            with self.subTest(url=url), self.assertRaises(CatalogError):
                github.validate_url(url, 'repo' if 'github.com/mainuan' in url or '/terceiro/' in url else None)
        with self.assertRaises(CatalogError):
            github.Redirects(None).redirect_request(None,None,302,'',{},github.API+'outro')
        github.validate_url('https://release-assets.githubusercontent.com/arquivo?assinatura=x', 'repo', redirect=True)

    def test_live_preparation_never_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            channel = github.GitHubChannel(Path(tmp), State())
            channel.online = True
            with patch.object(github, 'session_kind', return_value=SessionKind.LIVE), \
                 patch.object(github.os, 'geteuid', return_value=1000), patch.object(channel, 'plan') as plan:
                with self.assertRaisesRegex(CatalogError, 'Live'):
                    channel.prepare_plan(object(), Mock())
                plan.assert_not_called()


class NormalEntryTests(unittest.TestCase):
    def test_actual_normal_and_check_entry_select_channel_without_trial_or_config(self):
        driver = '''
import sys,json
from unittest.mock import patch
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from test_github_channel import Fixture,SYSTEM
from mainuan_recursos import application
from mainuan_recursos.session import SessionKind
from mainuan_recursos.gui import Window
fixture=Fixture()
original_exec=QApplication.exec
original_single=QTimer.singleShot
requested=[]
def schedule(ms,callback):
    requested.append(ms)
    original_single(0 if ms==60000 else ms,callback)
def execute(app):
    timer=QTimer()
    def inspect():
        windows=[w for w in app.topLevelWidgets() if isinstance(w,Window)]
        if windows and windows[0].current and not windows[0].worker:
            w=windows[0]
            assert w.github_channel is not None and w.github_trial is None
            assert w.install.isEnabled() and w.summary.text()==fixture.message
            assert w.automatic==('--check' in sys.argv)
            if w.automatic: assert 60000 in requested and w.timer.isActive()
            print('CANAL_NORMAL_OK')
            timer.stop();app.quit()
    timer.timeout.connect(inspect);timer.start(10)
    original_single(5000,lambda:app.exit(1))
    return original_exec()
with patch.object(application,'session_kind',return_value=SessionKind.INSTALLED), \
     patch('mainuan_recursos.github_channel.system_identity',return_value=SYSTEM), \
     patch('mainuan_recursos.gui.system_identity',return_value=SYSTEM), \
     patch('mainuan_recursos.github_channel.metadata',side_effect=fixture.metadata), \
     patch('apt.Cache',return_value={}), \
     patch('mainuan_recursos.github_trial.check_vm',side_effect=AssertionError('VM exigida')), \
     patch.object(application.Config,'load',side_effect=AssertionError('Config antiga exigida')), \
     patch.object(QTimer,'singleShot',side_effect=schedule), \
     patch.object(QApplication,'exec',execute):
    raise SystemExit(application.main(sys.argv[1:]))
'''
        for arguments in ([], ['--check']):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as tmp:
                env = {**os.environ, 'PYTHONPATH':'src:tests', 'QT_QPA_PLATFORM':'offscreen', 'XDG_STATE_HOME':tmp}
                result = subprocess.run([sys.executable,'-c',driver,*arguments],capture_output=True,text=True,env=env,timeout=10)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('CANAL_NORMAL_OK',result.stdout)
