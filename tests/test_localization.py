"""Localization contract: session language, gettext catalog and Qt standard buttons.

The test process runs with LANGUAGE=pt_BR (see i18n_support).  Tests that need
another language run the real code in a subprocess with its own environment.
"""
import gc
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import i18n_support
from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale
from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox, QPushButton

from mainuan_recursos import i18n
from mainuan_recursos.localization import install_translations, localize_standard_buttons
from qt_support import APP, wait_until

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location('preview_classic', ROOT / 'tools/preview-classic.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def run_python(code, language, *arguments, lc_all=None):
    """Run real application code in a fresh process for one session language."""
    env = {key: value for key, value in os.environ.items()
           if key not in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG')}
    env.update(PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'tests'))),
               QT_QPA_PLATFORM='offscreen', QT_STYLE_OVERRIDE='',
               MAINUAN_RECURSOS_LOCALEDIR=i18n_support.LOCALEDIR, LANG='C.UTF-8')
    if language is not None:
        env['LANGUAGE'] = language
    if lc_all is not None:
        env['LC_ALL'] = lc_all
    result = subprocess.run([sys.executable, '-c', code, *arguments], capture_output=True,
                            text=True, env=env, timeout=30)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


WINDOW_DRIVER = '''
from PyQt6.QtWidgets import QApplication, QDialogButtonBox
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.localization import install_translations
from mainuan_recursos.packages import RECEIVED, status_text
from mainuan_recursos.state import State
app = QApplication([])
install_translations(app)
window = Window(State(), demo=Demo())
close = window.history_dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
for value in (window.windowTitle(), window.install.text(), window.know.text(), window.later.text(),
              *[action.text() for action in window.view.menu.actions() if action.text()],
              window.options.accessibleName(), status_text(RECEIVED), close.text().replace('&', '')):
    print(value)
'''


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(lambda: install_translations(APP))

    def standard_buttons(self, cls):
        standard = cls.StandardButton
        return standard.Close | standard.Cancel | standard.Yes | standard.No

    def assert_portuguese(self, box):
        for name, text in (('Close', 'Fechar'), ('Cancel', 'Cancelar'), ('Yes', 'Sim'), ('No', 'Não')):
            button = box.button(getattr(box.StandardButton, name))
            self.assertEqual(button.text().replace('&', ''), text)

    def test_language_is_never_forced(self):
        before = QLocale().name()
        install_translations(APP, self.temporary.name)
        self.assertEqual(QLocale().name(), before)
        source = (ROOT / 'src/mainuan_recursos/localization.py').read_text()
        self.assertNotIn('setDefault', source)
        self.assertNotIn("'pt_BR'", source)

    def test_missing_qt_catalog_keeps_dialog_button_roles_and_signals(self):
        self.assertFalse(install_translations(APP, self.temporary.name))
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

    def test_native_catalog_for_session_locale_lives_for_application_lifetime(self):
        directory = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        if not (directory / 'qtbase_pt_BR.qm').exists():
            self.skipTest('Catálogo nativo pt_BR não instalado; alternativa testada separadamente.')
        self.assertTrue(install_translations(APP, locale=QLocale('pt_BR')))
        gc.collect()
        box = QDialogButtonBox(self.standard_buttons(QDialogButtonBox))
        self.addCleanup(box.deleteLater)
        box.show()
        APP.processEvents()
        self.assert_portuguese(box)
        box.close()

    def test_english_platform_theme_labels_are_fixed_before_show(self):
        install_translations(APP)
        box = QDialogButtonBox(self.standard_buttons(QDialogButtonBox))
        self.addCleanup(box.deleteLater)
        for name in ('Close', 'Cancel', 'Yes', 'No'):
            box.button(getattr(box.StandardButton, name)).setText(name)
        box.show()
        APP.processEvents()
        self.assert_portuguese(box)
        box.close()

    def test_native_translation_has_priority_over_catalog_fallback(self):
        install_translations(APP, self.temporary.name)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.addCleanup(box.deleteLater)
        box.button(QDialogButtonBox.StandardButton.Close).setText('Close')
        with patch('mainuan_recursos.localization.QCoreApplication.translate', return_value='Schließen') as translate:
            localize_standard_buttons(box)
        translate.assert_called_once_with('QPlatformTheme', 'Close')
        self.assertEqual(box.buttons()[0].text(), 'Schließen')

    def test_fallback_comes_from_the_gettext_catalog_not_a_fixed_language(self):
        install_translations(APP, self.temporary.name)
        box = QDialogButtonBox(self.standard_buttons(QDialogButtonBox))
        self.addCleanup(box.deleteLater)
        with patch.dict(os.environ, {'LANGUAGE': 'en'}):
            i18n.reload()
            try:
                localize_standard_buttons(box)
            finally:
                os.environ['LANGUAGE'] = 'pt_BR'
                i18n.reload()
        for name, text in (('Close', 'Close'), ('Cancel', 'Cancel'), ('Yes', 'Yes'), ('No', 'No')):
            self.assertEqual(box.button(getattr(box.StandardButton, name)).text().replace('&', ''), text)

    def test_warning_error_question_and_success_message_boxes(self):
        install_translations(APP, self.temporary.name)
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
        install_translations(APP, self.temporary.name)
        self.assertEqual(QCoreApplication.translate('Mainuan', 'Texto de exemplo'), 'Texto de exemplo')
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.addCleanup(box.deleteLater)
        box.button(QDialogButtonBox.StandardButton.Close).setText('Voltar')
        localize_standard_buttons(box)
        self.assertEqual(box.buttons()[0].text(), 'Voltar')

    def test_preview_postpone_and_technical_dialogs_close_in_portuguese(self):
        install_translations(APP, self.temporary.name)
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
        install_translations(APP, self.temporary.name)
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


class SessionLanguageTests(unittest.TestCase):
    """Real code in fresh processes: pt_BR shows the original text, en/C show English."""

    PORTUGUESE = ['Atualizador de Recursos do Mainuan — Demonstração', 'Instalar novidades', 'Conhecer novidades',
                  'Agora não', 'Verificar novidades', 'Histórico de novidades', 'Informações técnicas',
                  'Mais opções', 'Já recebido', 'Fechar']
    ENGLISH = ['Mainuan Feature Updater — Demo', 'Install New Features', 'Discover What’s New', 'Not Now',
               'Check for News', 'News History', 'Technical Information', 'More Options',
               'Already received', 'Close']

    def window_texts(self, language, lc_all=None):
        return run_python(WINDOW_DRIVER, language, lc_all=lc_all).splitlines()

    def test_window_in_brazilian_portuguese(self):
        self.assertEqual(self.window_texts('pt_BR'), self.PORTUGUESE)

    def test_window_in_english_and_c_locale(self):
        self.assertEqual(self.window_texts('en'), self.ENGLISH)
        self.assertEqual(self.window_texts(None, lc_all='C'), self.ENGLISH)

    def test_unknown_language_falls_back_to_english_not_portuguese(self):
        self.assertEqual(self.window_texts('xx_YY'), self.ENGLISH)

    def test_right_to_left_catalog_mirrors_without_qtbase(self):
        code = '''
import tempfile
from PyQt6.QtWidgets import QApplication
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.localization import install_translations
from mainuan_recursos.state import State
app = QApplication([])
with tempfile.TemporaryDirectory() as empty:
    # Empty Qt translations directory: no qtbase_<lang>.qm can mirror the layout.
    print(install_translations(app, empty))
window = Window(State(), demo=Demo())
print(app.layoutDirection().name, window.isRightToLeft())
'''
        # The application's Arabic catalog is used: mirrored even without qtbase_ar.
        self.assertEqual(run_python(code, 'ar').split(), ['False', 'RightToLeft', 'True'])
        # Urdu has an application catalog but no qtbase_ur: mirrored by the catalog.
        self.assertEqual(run_python(code, 'ur').split(), ['False', 'RightToLeft', 'True'])
        # Yiddish is right-to-left but has no application catalog: English, left to right.
        self.assertEqual(run_python(code, 'yi').split(), ['False', 'LeftToRight', 'False'])

    def test_command_line_help(self):
        code = 'from mainuan_recursos.application import main; main()'
        self.assertIn('Conheça e receba as novidades oficiais do Mainuan.', run_python(code, 'pt_BR', '--help'))
        self.assertIn('Discover and receive the official Mainuan news.', run_python(code, 'en', '--help'))

    def test_error_messages_and_package_status(self):
        code = '''
from mainuan_recursos.catalog import CatalogError, decode
from mainuan_recursos.packages import INSTALL, status_text
try:
    decode(b'x' * (1024 * 1024 + 1))
except CatalogError as exc:
    print(exc)
print(status_text(INSTALL))
'''
        self.assertEqual(run_python(code, 'pt_BR').splitlines(), ['Catálogo excede o limite de tamanho.', 'Instalar'])
        self.assertEqual(run_python(code, 'en').splitlines(), ['The catalog exceeds the size limit.', 'Install'])


class DesktopEntryTests(unittest.TestCase):
    def test_generated_desktop_entries_keep_the_original_portuguese_text(self):
        expected = {
            'org.mainuan.Recursos.desktop.in': ('Atualizador de Recursos do Mainuan',
                                                'Conheça e receba as novidades oficiais do Mainuan'),
            'mainuan-recursos-autostart.desktop.in': ('Novidades do Mainuan', 'Verifica novidades durante a sessão'),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for template, (name, comment) in expected.items():
                with self.subTest(template=template):
                    output = Path(tmp) / template[:-3]
                    subprocess.run(['msgfmt', '--desktop', '--template', str(ROOT / 'data' / template),
                                    '-d', str(ROOT / 'po'), '-o', str(output)], check=True)
                    lines = output.read_text().splitlines()
                    self.assertIn(f'Name[pt_BR]={name}', lines)
                    self.assertIn(f'Comment[pt_BR]={comment}', lines)
                    self.assertFalse(any(line.startswith('Name=') and 'Mainuan' not in line for line in lines))


if __name__ == '__main__':
    unittest.main()
