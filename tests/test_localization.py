import gc
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QCoreApplication, QLibraryInfo
from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox, QPushButton

from mainuan_recursos.localization import install_pt_br, localize_standard_buttons
from qt_support import APP, wait_until


spec = importlib.util.spec_from_file_location('preview_classic',
    Path(__file__).resolve().parents[1] / 'tools/preview-classic.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(lambda: install_pt_br(APP))

    def standard_buttons(self, cls):
        standard = cls.StandardButton
        return standard.Close | standard.Cancel | standard.Yes | standard.No

    def assert_portuguese(self, box):
        for name, text in (('Close', 'Fechar'), ('Cancel', 'Cancelar'), ('Yes', 'Sim'), ('No', 'Não')):
            button = box.button(getattr(box.StandardButton, name))
            self.assertEqual(button.text().replace('&', ''), text)

    def test_missing_qt_catalog_keeps_dialog_button_roles_and_signals(self):
        self.assertFalse(install_pt_br(APP, self.temporary.name))
        box = QDialogButtonBox(self.standard_buttons(QDialogButtonBox))
        self.addCleanup(box.deleteLater)
        box.show()
        APP.processEvents()
        self.assert_portuguese(box)
        rejected = []
        box.rejected.connect(lambda: rejected.append(True))
        close = box.button(QDialogButtonBox.StandardButton.Close)
        self.assertEqual(box.buttonRole(close), QDialogButtonBox.ButtonRole.RejectRole)
        close.click()
        self.assertEqual(rejected, [True])
        box.close()

    def test_native_catalog_lives_for_application_lifetime(self):
        directory = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        if not (directory / 'qtbase_pt_BR.qm').exists():
            self.skipTest('Catálogo nativo pt_BR não instalado; alternativa testada separadamente.')
        self.assertTrue(install_pt_br(APP))
        gc.collect()
        box = QDialogButtonBox(self.standard_buttons(QDialogButtonBox))
        self.addCleanup(box.deleteLater)
        box.show()
        APP.processEvents()
        self.assert_portuguese(box)
        box.close()

    def test_english_platform_theme_labels_are_fixed_before_show(self):
        install_pt_br(APP)
        box = QDialogButtonBox(self.standard_buttons(QDialogButtonBox))
        self.addCleanup(box.deleteLater)
        for name in ('Close', 'Cancel', 'Yes', 'No'):
            box.button(getattr(box.StandardButton, name)).setText(name)
        box.show()
        APP.processEvents()
        self.assert_portuguese(box)
        box.close()

    def test_native_translation_has_priority_over_explicit_fallback(self):
        install_pt_br(APP, self.temporary.name)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.addCleanup(box.deleteLater)
        box.button(QDialogButtonBox.StandardButton.Close).setText('Close')
        with patch('mainuan_recursos.localization.QCoreApplication.translate', return_value='Fechar') as translate:
            localize_standard_buttons(box)
        translate.assert_called_once_with('QPlatformTheme', 'Close')
        self.assertEqual(box.buttons()[0].text(), 'Fechar')

    def test_warning_error_question_and_success_message_boxes(self):
        install_pt_br(APP, self.temporary.name)
        for icon in (QMessageBox.Icon.Information, QMessageBox.Icon.Warning,
                     QMessageBox.Icon.Critical, QMessageBox.Icon.Question):
            with self.subTest(icon=icon):
                message = QMessageBox()
                message.setIcon(icon)
                message.setText('Mensagem em português brasileiro.')
                message.setStandardButtons(self.standard_buttons(QMessageBox))
                message.show()
                APP.processEvents()
                self.assert_portuguese(message)
                message.close()
                message.deleteLater()

    def test_custom_labels_and_unrelated_translations_are_preserved(self):
        install_pt_br(APP, self.temporary.name)
        self.assertEqual(QCoreApplication.translate('Mainuan', 'Texto de exemplo'), 'Texto de exemplo')
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.addCleanup(box.deleteLater)
        box.button(QDialogButtonBox.StandardButton.Close).setText('Voltar')
        localize_standard_buttons(box)
        self.assertEqual(box.buttons()[0].text(), 'Voltar')

    def test_preview_postpone_and_technical_dialogs_close_in_portuguese(self):
        install_pt_br(APP, self.temporary.name)
        window = preview.Preview('Mensagem de exemplo.')
        self.addCleanup(window.deleteLater)
        window.show()
        window.later.click()
        later = window.dialogs[-1]
        close = later.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
        self.assertEqual(close.text().replace('&', ''), 'Fechar')
        rejected = []
        later.rejected.connect(lambda: rejected.append(True))
        close.click()
        self.assertEqual(rejected, [True])
        technical = window.technical()
        box = technical.findChild(QDialogButtonBox)
        self.assertEqual(box.button(QDialogButtonBox.StandardButton.Close).text().replace('&', ''), 'Fechar')
        technical.reject()
        window.close()

    def test_preview_cancel_and_success_keep_their_actions(self):
        install_pt_br(APP, self.temporary.name)
        window = preview.Preview('Mensagem de exemplo.')
        self.addCleanup(window.deleteLater)
        window.show()
        confirmation = window.confirmation()
        box = confirmation.findChild(QDialogButtonBox)
        cancel = next(b for b in box.buttons() if b.text() == 'Cancelar')
        self.assertEqual(box.buttonRole(cancel), QDialogButtonBox.ButtonRole.RejectRole)
        cancel.click()
        self.assertFalse(window.dialogs)
        confirmation = window.confirmation()
        simulate = next(b for b in confirmation.findChildren(QPushButton) if b.text() == 'Simular conclusão')
        simulate.click()
        wait_until(lambda: bool(window.dialogs) and 'concluída' in window.dialogs[-1].windowTitle())
        success = window.dialogs[-1]
        close = success.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
        self.assertEqual(close.text().replace('&', ''), 'Fechar')
        close.click()
        window.close()
