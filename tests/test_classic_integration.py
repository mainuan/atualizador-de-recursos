import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialogButtonBox, QPushButton, QTreeWidget

from helpers import catalog_dict, package
from mainuan_recursos.catalog import Config
from mainuan_recursos.classic import ClassicContent, ILLUSTRATION
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.state import State
from qt_support import APP, wait_until
from test_localization import preview


class ClassicIntegrationTests(unittest.TestCase):
    def create(self, scenario='novo'):
        demo = Demo(scenario)
        window = Window(State(), demo=demo)
        self.addCleanup(window.deleteLater)
        window.show()
        window.reload()
        wait_until(lambda: window.worker is None)
        APP.processEvents()
        return window, demo

    def test_normal_loader_uses_authenticated_catalog_not_preview_examples(self):
        now = datetime.now(timezone.utc)
        obj = catalog_dict()
        obj['published_at'] = now.isoformat()
        obj['expires_at'] = (now + timedelta(days=7)).isoformat()
        obj['releases'][0]['summary'] = 'Mensagem real do catálogo <b>em texto simples</b>.\nSegunda linha.'
        obj['releases'][0]['features'][0]['title'] = 'Programa com nome editorial próprio'
        raw = json.dumps(obj).encode()
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        signature = json.dumps({'key_id': 'teste', 'signature': base64.b64encode(key.sign(raw)).decode()}).encode()
        config = Config('https://mainuan.example/catalog.json', ('mainuan.example',),
                        {'teste': base64.b64encode(public).decode()})
        cache = {p['name']: package(candidate=p['min_version'])
                 for f in obj['releases'][0]['features'] for p in f['packages']}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            state = State(directory / 'state.json')
            window = Window(state, directory)
            self.addCleanup(window.deleteLater)
            window.show()
            with patch('mainuan_recursos.gui.Config.load', return_value=config), \
                 patch('mainuan_recursos.repository.fetch', return_value=(raw, signature)), \
                 patch('mainuan_recursos.gui.system_identity', return_value={
                     'distro_id': 'mainuan', 'version_id': '26.04', 'architecture': 'amd64'}), \
                 patch('apt.Cache', return_value=cache):
                window.reload()
                wait_until(lambda: window.worker is None)
            self.assertIsNone(window.demo)
            self.assertEqual(window.summary.text(), obj['releases'][0]['summary'])
            self.assertEqual(window.summary.textFormat(), Qt.TextFormat.PlainText)
            self.assertEqual(window.program_labels[0].text(), '•  Programa com nome editorial próprio')
            self.assertEqual(state.data['sequence'], obj['sequence'])
            self.assertEqual(state.entry(window.current)['packages'], 'pending')
            self.assertEqual(state.entry(window.current)['presentation'], 'viewed')
            self.assertFalse(window.view.findChildren(QTreeWidget))
            self.assertTrue(window.install.isEnabled())
            window.details_action.trigger()
            self.assertIn('mainuan-boas-vindas', window.details_text.toPlainText())
            self.assertIn('1.2.0', window.details_text.toPlainText())
            self.assertIn('Instalar', window.details_text.toPlainText())
            window.details_dialog.reject()
            window.close()

    def test_approved_component_and_geometry_are_shared_with_preview(self):
        window, _ = self.create()
        fixture = preview.Preview(window.current.summary,
                                  programs=tuple((f.title, f.packages[0].name) for f in window.current.features))
        self.addCleanup(fixture.deleteLater)
        fixture.show()
        APP.processEvents()
        self.assertIs(type(window.view), ClassicContent)
        self.assertIs(type(fixture.view), ClassicContent)
        self.assertEqual(window.size(), fixture.size())
        for actual, reference in zip((window.summary, window.illustration, window.know, window.install, window.later),
                                     (fixture.message, fixture.illustration, fixture.know, fixture.install, fixture.later)):
            self.assertEqual(actual.size(), reference.size())
            self.assertEqual(actual.mapTo(window, actual.rect().topLeft()),
                             reference.mapTo(fixture, reference.rect().topLeft()))
        fixture.close()
        window.close()

    def test_resource_belongs_to_application_and_has_original_alpha(self):
        window, _ = self.create()
        self.assertEqual(ILLUSTRATION.parent.parent, Path(__import__('mainuan_recursos.classic', fromlist=['']).__file__).parent)
        self.assertEqual(hashlib.sha256(ILLUSTRATION.read_bytes()).hexdigest(),
                         'ab18dab7009c85a72bd7b35cdd74f08fcd339bdc3ea0647b987c7f03d53c6c2b')
        self.assertTrue(window.illustration.pixmap.hasAlphaChannel())
        window.close()

    def test_menu_opens_real_history_details_and_refresh(self):
        window, demo = self.create('instalado')
        self.assertEqual([a.text() for a in window.view.menu.actions() if not a.isSeparator()],
                         ['Verificar novidades', 'Histórico de novidades', 'Informações técnicas'])
        self.assertFalse(window.history.isVisible())
        window.history_action.trigger()
        self.assertTrue(window.history.isVisible())
        window.history.setCurrentRow(1)
        self.assertEqual(window.current.key, demo.catalog.releases[1].key)
        self.assertEqual(window.summary.text(), window.current.summary)
        window.history_dialog.reject()
        window.details_action.trigger()
        self.assertTrue(window.details_dialog.isVisible())
        self.assertIn('Já recebido', window.details_text.toPlainText())
        self.assertIn(window.current.packages[0].min_version, window.details_text.toPlainText())
        box = window.details_dialog.findChild(QDialogButtonBox)
        close = box.button(QDialogButtonBox.StandardButton.Close)
        self.assertEqual(close.text().replace('&', ''), 'Fechar')
        close.click()
        self.assertFalse(window.details_dialog.isVisible())
        demo.catalog = replace(demo.catalog, sequence=2, digest='f' * 64)
        window.refresh.trigger()
        wait_until(lambda: window.worker is None)
        self.assertEqual(window.state.data['sequence'], 2)
        self.assertFalse(window.install.isEnabled())
        window.close()

    def test_real_install_button_can_cancel_without_marking_installed(self):
        window, _ = self.create()
        def cancel():
            dialog = APP.activeModalWidget()
            if dialog:
                next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Cancelar').click()
                timer.stop()
        timer = QTimer()
        timer.timeout.connect(cancel)
        timer.start(10)
        window.install.click()
        wait_until(lambda: window.controller.awaiting is None and not window.controller.busy)
        timer.stop()
        self.assertEqual(window.state.entry(window.current)['packages'], 'pending')
        self.assertIn('cancelada', window.status.text())
        window.close()

    def test_postpone_hides_auxiliary_windows_and_keeps_resource_state(self):
        window, _ = self.create()
        window.history_action.trigger()
        window.details_action.trigger()
        self.assertTrue(window.history_dialog.isVisible())
        self.assertTrue(window.details_dialog.isVisible())
        window.later.click()
        self.assertFalse(window.isVisible())
        self.assertFalse(window.history_dialog.isVisible())
        self.assertFalse(window.details_dialog.isVisible())
        self.assertEqual(window.state.entry(window.current)['presentation'], 'postponed')
        self.assertEqual(window.state.entry(window.current)['packages'], 'pending')
