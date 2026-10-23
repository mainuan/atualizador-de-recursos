from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt

from mainuan_recursos.application import main
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.session import SessionKind, is_live_session, session_kind
from mainuan_recursos.state import State
from qt_support import APP, wait_until


class SessionTests(unittest.TestCase):
    def test_live_kernel_parameters(self):
        for cmdline in ('quiet boot=casper splash', 'boot=live'):
            with patch.object(Path, 'read_text', return_value=cmdline):
                self.assertTrue(is_live_session())

    def test_normal_root_is_not_live_even_with_mounted_media(self):
        def read(path):
            return 'quiet splash' if str(path) == '/proc/cmdline' else '1 0 8:1 / / rw - ext4 /dev/sda1 rw'
        with patch.object(Path, 'read_text', read), patch.object(Path, 'exists', return_value=True):
            self.assertEqual(session_kind(), SessionKind.INSTALLED)
            self.assertFalse(is_live_session())

    def test_live_autostart_exits_before_application_or_network(self):
        for kind in (SessionKind.LIVE, SessionKind.UNKNOWN):
            with patch('mainuan_recursos.application.session_kind', return_value=kind), patch('mainuan_recursos.application.QApplication') as app:
                self.assertEqual(main(['--check']),0)
                app.assert_not_called()


class WindowTests(unittest.TestCase):
    def create(self, scenario='novo', automatic=False):
        demo = Demo(scenario)
        state = State()
        window = Window(state, automatic=automatic, demo=demo)
        self.addCleanup(window.deleteLater)
        return window, demo, state

    def load(self, window):
        window.reload()
        wait_until(lambda:window.worker is None)

    def test_demo_constructs_no_dbus_apt_or_network(self):
        with patch('mainuan_recursos.packagekit.QtDBus.QDBusConnection.systemBus', side_effect=AssertionError('D-Bus proibido')), \
             patch('mainuan_recursos.catalog.fetch', side_effect=AssertionError('Rede proibida')), \
             patch('apt.Cache', side_effect=AssertionError('APT proibido')):
            window,_,_ = self.create()
            self.load(window)
            window.controller.prepared.disconnect(window._confirm)
            window.prepare()
            wait_until(lambda:window.controller.awaiting is not None)
            window.controller.cancel_preparation()

    def test_native_labels_features_and_plain_catalog_text(self):
        window,demo,state = self.create()
        self.load(window)
        self.assertEqual(window.know.text(),'Conhecer novidades')
        self.assertEqual(window.install.text(),'Instalar novidades')
        self.assertEqual(window.later.text(),'Agora não')
        self.assertTrue(window.install.isEnabled())
        self.assertEqual(window.summary.textFormat(),Qt.TextFormat.PlainText)
        self.assertEqual(len(window.program_labels),3)
        self.assertEqual(window.summary.text(),demo.release.summary)
        self.assertEqual(window.history.count(),2)

    def test_received_unavailable_incompatible(self):
        for scenario in ('instalado','indisponivel','incompativel'):
            window,_,_ = self.create(scenario)
            self.load(window)
            self.assertFalse(window.install.isEnabled())
            self.assertTrue(window.know.isEnabled())

    def test_offline_catalog_disables_installation(self):
        window,_,_ = self.create()
        self.load(window)
        window.online = False
        window.select(0)
        self.assertFalse(window.install.isEnabled())
        self.assertIn('offline',window.status.text())

    def test_automatic_new_release_visible_and_viewed(self):
        window,demo,state = self.create(automatic=True)
        state.viewed(demo.catalog.releases[1])
        self.load(window)
        self.assertTrue(window.isVisible())
        self.assertFalse(state.due(demo.release))
        window.close()
        self.assertFalse(window.isVisible())
        self.load(window)
        self.assertFalse(window.isVisible())

    def test_postponement_and_manual_history(self):
        window,demo,state = self.create(automatic=True)
        for release in demo.catalog.releases:
            state.postpone(release)
        self.load(window)
        self.assertFalse(window.isVisible())
        window.show()
        self.assertTrue(window.know.isEnabled())
        self.assertEqual(state.entry(demo.release)['presentation'],'postponed')
        window.postpone()
        self.assertFalse(window.isVisible())

    def test_article_uses_default_browser(self):
        window,demo,state = self.create()
        self.load(window)
        with patch('mainuan_recursos.gui.QDesktopServices.openUrl', return_value=True) as open_url:
            window.open_article()
            self.assertEqual(open_url.call_args.args[0].toString(),demo.release.article_url)

    def test_full_demo_flow_without_redundant_confirmation_and_verified_status(self):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication, QDialog, QPushButton
        window,demo,state = self.create()
        self.load(window)
        window.show()
        clicked = []
        timer = QTimer()
        def approve():
            modal = QApplication.activeModalWidget()
            if isinstance(modal, QDialog):
                button = next((b for b in modal.findChildren(QPushButton) if b.text() == 'Instalar novidades'),None)
                if button:
                    clicked.append(True)
                    QTest.mouseClick(button,Qt.MouseButton.LeftButton)
                    timer.stop()
        timer.timeout.connect(approve)
        timer.start(10)
        window.prepare()
        wait_until(lambda:demo.installed and not window.controller.busy)
        timer.stop()
        self.assertFalse(clicked)
        self.assertEqual(state.entry(demo.release)['packages'],'installed')
        self.assertFalse(window.install.isEnabled())
        self.assertEqual(window.status.text(),'Concluído! Aproveite os novos recursos do Mainuan.')
        window.close()

    def test_state_write_failure_shown_without_crashing_widgets(self):
        window,_,state = self.create()
        self.load(window)
        state.entry(window.current)['presentation'] = 'unseen'
        with patch.object(state, 'save', side_effect=OSError('Sem espaço')):
            window.mark_viewed()
            self.assertIn('Não foi possível salvar',window.status.text())
            window.postpone()
            self.assertIn('adiamento',window.status.text())
