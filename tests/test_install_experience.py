"""Regressões do clique de instalar, download tardio e apresentação clássica."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from mainuan_recursos import github_trial as github
from mainuan_recursos.catalog import CatalogError
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.packages import Plan, PackageRow
from mainuan_recursos.state import State
from qt_support import APP, wait_until


def pending():
    return Plan((PackageRow(github.NAME, '1.0', '', '1.0', 'all', 'Instalar', github.SHA256),))


class LazyDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.trial = github.GitHubTrial(Path(self.temporary.name))

    def test_initial_consultation_fetches_only_metadata(self):
        sha = 'a' * 40
        responses = {
            'https://api.github.com/repos/mainuan/atualizadorderecursos/commits/main':
                json.dumps({'sha': sha, 'commit': {'committer': {'date': datetime.now(timezone.utc).isoformat()}}}).encode(),
            f'https://raw.githubusercontent.com/mainuan/atualizadorderecursos/{sha}/packages.txt': b'mainuan-gestao-drivers\n',
            f'https://raw.githubusercontent.com/mainuan/atualizadorderecursos/{sha}/message.txt': 'Olá! Confira as novidades:'.encode(),
            f'https://api.github.com/repos/mainuan/{github.REPOSITORY}': json.dumps({
                'id': 1405529794, 'full_name': 'mainuan/mainuan-gestao-drivers', 'owner': {'login': 'mainuan'}}).encode(),
            f'https://api.github.com/repos/mainuan/{github.REPOSITORY}/releases/{github.RELEASE_ID}': json.dumps({
                'id': github.RELEASE_ID, 'tag_name': 'v1.0', 'published_at': '2026-10-22T21:24:02Z',
                'assets': [{'id': github.ASSET_ID, 'name': self.trial.path.name, 'size': github.SIZE,
                            'digest': 'sha256:' + github.SHA256, 'browser_download_url': github.ASSET_URL}]}).encode(),
        }
        with patch.object(github, 'download', side_effect=lambda url, *a, **k: responses[url]) as download:
            catalog, online = self.trial.load()
        self.assertTrue(online)
        self.assertEqual(catalog.releases[0].features[0].title, 'Gestão de Drivers 1.0')
        self.assertFalse(self.trial.path.parent.exists())
        self.assertNotIn(github.ASSET_URL, [call.args[0] for call in download.call_args_list])

    def test_initial_plan_does_not_read_or_require_deb(self):
        release = object(); self.trial.release = release
        with patch('apt.Cache', return_value={}), patch.object(self.trial, 'verify_file') as verify:
            self.assertEqual(self.trial.plan(release).rows[0].status, 'Instalar')
        verify.assert_not_called()
        self.assertFalse(self.trial.path.exists())

    def test_package_is_downloaded_only_during_preparation(self):
        payload = b'pacote ficticio, nunca instalado'
        progress = Mock()
        with patch.object(self.trial, 'plan', side_effect=[pending(), pending()]) as plan, \
             patch.object(github, 'supports_local_files'), \
             patch.object(github, 'SHA256', hashlib.sha256(payload).hexdigest()), \
             patch.object(github, 'SIZE', len(payload)), patch.object(github, 'download', return_value=payload) as download:
            self.trial.prepare_plan(object(), progress)
        self.assertEqual(self.trial.path.read_bytes(), payload)
        self.assertEqual(download.call_count, 1)
        self.assertTrue(plan.call_args.kwargs['check_dependencies'])
        self.assertIn(('Baixando novidades...', 0), [call.args for call in progress.call_args_list])

    def test_already_received_skips_download_and_backend(self):
        received = Plan((PackageRow(github.NAME, '1.0', '1.0', '1.0', 'all', 'Já recebido'),))
        with patch.object(self.trial, 'plan', return_value=received), \
             patch.object(github, 'download') as download, patch.object(github, 'supports_local_files') as support:
            self.assertTrue(self.trial.prepare_plan(object(), Mock()).complete)
        download.assert_not_called(); support.assert_not_called()

    def test_corrupt_download_is_not_cached_or_prepared(self):
        with patch.object(self.trial, 'plan', return_value=pending()), \
             patch.object(github, 'supports_local_files'), patch.object(github, 'download', return_value=b'alterado'):
            with self.assertRaisesRegex(CatalogError, 'integridade'):
                self.trial.prepare_plan(object(), Mock())
        self.assertFalse(self.trial.path.exists())

    def test_corrupt_cached_file_is_rejected_before_simulation(self):
        self.trial.path.parent.mkdir(); self.trial.path.write_bytes(b'corrompido')
        with patch.object(self.trial, 'plan', return_value=pending()), patch.object(github, 'supports_local_files'), \
             patch.object(github, 'download') as download:
            with self.assertRaisesRegex(CatalogError, 'Integridade'):
                self.trial.prepare_plan(object(), Mock())
        download.assert_not_called()

    def test_download_emits_real_byte_progress_and_keeps_size_limit(self):
        payload = b'x' * 190846
        opener = Mock(); opener.open.return_value = io.BytesIO(payload)
        progress = []
        with patch.object(github, 'build_opener', return_value=opener):
            self.assertEqual(github.download(github.ASSET_URL, len(payload), binary=True, progress=progress.append), payload)
        self.assertTrue(any(0 < value < 100 for value in progress))
        self.assertEqual(progress[-1], 100)
        opener.open.return_value = io.BytesIO(payload + b'x')
        with patch.object(github, 'build_opener', return_value=opener), self.assertRaisesRegex(CatalogError, 'tamanho'):
            github.download(github.ASSET_URL, len(payload), binary=True)

    def test_post_install_verification_never_downloads_again(self):
        trial = Mock()
        controller = github.GitHubController(trial)
        self.addCleanup(controller.deleteLater)
        release = object()
        controller.verification_plan(release)
        trial.plan.assert_called_once_with(release)
        trial.prepare_plan.assert_not_called()


class InstallExperienceTests(unittest.TestCase):
    def create(self, scenario='novo'):
        demo = Demo(scenario)
        window = Window(State(), demo=demo)
        self.addCleanup(window.deleteLater)
        window.show(); window.reload()
        wait_until(lambda: window.worker is None)
        return window, demo

    def test_buttons_have_requested_order_uniform_geometry_and_native_primary(self):
        window, _ = self.create()
        buttons = window.view.buttons
        self.assertEqual([button.text() for button in buttons], ['Instalar novidades', 'Conhecer novidades', 'Agora não'])
        self.assertEqual(len({(b.width(), b.height()) for b in buttons}), 1)
        self.assertEqual(len({b.mapTo(window, b.rect().topRight()).x() for b in buttons}), 1)
        gaps = [buttons[i + 1].y() - buttons[i].geometry().bottom() for i in (0, 1)]
        self.assertEqual(gaps[0], gaps[1])
        self.assertTrue(all(not b.isFlat() for b in buttons))
        self.assertTrue(window.install.isDefault() and window.install.font().bold())
        self.assertFalse(window.know.isDefault() or window.know.font().bold())
        self.assertIs(window.focusWidget(), window.install)
        with patch.object(window.controller, 'prepare') as prepare:
            QTest.keyClick(window.install, Qt.Key.Key_Return)
            prepare.assert_called_once_with(window.current)
        window.close()

    def test_trust_explanation_is_only_in_technical_menu(self):
        from PyQt6.QtWidgets import QLabel
        window, _ = self.create()
        window.demo = None
        window.github_trial = object()
        main_text = '\n'.join(item.text() for item in window.view.findChildren(QLabel))
        for technical in ('SHA-256', 'assinatura de repositório', 'origem não confiável'):
            self.assertNotIn(technical, main_text)
        window.details_action.trigger()
        self.assertIn('SHA-256', window.details_text.toPlainText())
        self.assertIn('origem não confiável', window.details_text.toPlainText())
        window.close()

    def test_single_click_revalidates_twice_then_installs_without_modal(self):
        window, demo = self.create()
        calls = []
        original = window.controller.transaction_factory
        def factory(parent):
            tx = original(parent); start = tx.start
            def record(method, values, simulate=False, authorized=False):
                calls.append((method, simulate, authorized))
                start(method, values, simulate=simulate, authorized=authorized)
            tx.start = record
            return tx
        window.controller.transaction_factory = factory
        with patch.object(QDialog, 'exec', side_effect=AssertionError('Confirmação redundante')):
            QTest.mouseClick(window.install, Qt.MouseButton.LeftButton)
            wait_until(lambda: demo.installed and not window.controller.busy)
        self.assertEqual(sum(method == 'InstallPackages' and simulate for method, simulate, _ in calls), 2)
        self.assertEqual(sum(method == 'InstallPackages' and not simulate and authorized for method, simulate, authorized in calls), 1)
        self.assertEqual(window.status.text(), 'Concluído! Aproveite os novos recursos do Mainuan.')
        self.assertEqual(window.state.entry(demo.release)['packages'], 'installed')
        window.close()

    def test_authorization_cancel_and_failure_do_not_report_success(self):
        for scenario in ('cancelado', 'erro'):
            with self.subTest(scenario=scenario):
                window, demo = self.create(scenario)
                window.install.click()
                wait_until(lambda: not window.controller.busy and not window.controller.awaiting)
                self.assertFalse(demo.installed)
                self.assertNotIn('Concluído!', window.status.text())
                self.assertEqual(window.state.entry(demo.release)['packages'], 'pending')
                window.close()
