"""Anúncio explícito: a janela automática só abre para announcements.json ativo.

Cobre: nenhum anúncio (404), desativado, ativo, já lido, nova versão, sem rede,
GitHub indisponível, JSON inválido, arquivo grande demais, URL não oficial,
tradução, sessão Live, preferência desligada e o processo do autostart que
encerra sozinho.  Nada aqui acessa a rede, o APT ou o D-Bus de verdade.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from qt_support import APP, wait_until
from mainuan_recursos import announcement as announcements
from mainuan_recursos import github_channel as github
from mainuan_recursos.application import main
from mainuan_recursos.catalog import CatalogError
from mainuan_recursos.gui import Window
from mainuan_recursos.preferences import Preferences
from mainuan_recursos.session import SessionKind
from mainuan_recursos.state import State
from test_github_channel import Fixture, SYSTEM

ROOT = Path(__file__).resolve().parents[1]
URL = f'https://raw.githubusercontent.com/mainuan/{github.OFFICIAL}/' + 'a' * 40 + '/announcements.json'


def active(**changes):
    value = {'schema': 1, 'enabled': True, 'id': 'boas-vindas', 'version': 1,
             'title': {'pt_BR': 'Novidade', 'en': 'News'},
             'message': {'pt_BR': 'Texto', 'en': 'Text'}}
    value.update(changes)
    return value


def parse(value):
    return announcements.parse(json.dumps(value).encode() if not isinstance(value, bytes) else value)


class ParseTests(unittest.TestCase):
    def test_published_file_in_repository_is_disabled(self):
        # O arquivo publicado na main faz parte da entrega: começa desativado.
        self.assertIsNone(announcements.parse((ROOT / 'announcements.json').read_bytes()))

    def test_disabled_ignores_drafts_but_not_the_format(self):
        self.assertIsNone(parse({'schema': 1, 'enabled': False, 'id': '', 'title': {}}))
        for value in ({'schema': 2, 'enabled': False}, {'schema': 1, 'enabled': 'false'},
                      {'schema': 1, 'enabled': 0}, {'enabled': False}, {'schema': 1, 'enabled': False, 'extra': 1}, []):
            with self.subTest(value=value), self.assertRaises(CatalogError):
                parse(value)

    def test_active_announcement(self):
        item = parse(active(url='https://mainuan.github.io/novidades/2027.html', packages=['mainuan-gestao-drivers'],
                            applies_to={'version_id': ['2027.1']}))
        self.assertEqual(item.key, 'boas-vindas@1')
        self.assertEqual(item.packages, ('mainuan-gestao-drivers',))
        self.assertEqual(item.localized(['pt_BR', 'pt']), ('Novidade', 'Novidade\n\nTexto'))
        self.assertTrue(item.applies({'distro_id': 'mainuan', 'version_id': '2027.1'}))
        self.assertFalse(item.applies({'distro_id': 'mainuan', 'version_id': '26.04'}))
        self.assertTrue(parse(active()).applies({}))

    def test_title_without_message_and_plain_text_kept_verbatim(self):
        item = parse(active(title={'pt_BR': '<b>Olá</b> <a href="x">link</a>'}, message={}))
        self.assertEqual(item.localized(['pt_BR']), ('<b>Olá</b> <a href="x">link</a>',) * 2)

    def test_translation_choice(self):
        item = parse(active(title={'pt_BR': 'Olá', 'en': 'Hello', 'ja': 'こんにちは', 'zh_TW': '你好'},
                            message={'pt_BR': 'a', 'en': 'b'}))
        self.assertEqual(item.localized(['ja_JP', 'ja'])[1], 'こんにちは')
        self.assertEqual(item.localized(['zh_TW', 'zh'])[0], '你好')
        self.assertEqual(item.localized(['it_IT', 'it'])[0], 'Hello')
        self.assertEqual(item.localized(['pt_PT', 'pt'])[0], 'Olá')
        self.assertEqual(item.localized(['en_US', 'en', 'pt_BR', 'pt'])[1], 'Hello\n\nb')
        self.assertEqual(item.localized([])[0], 'Hello')
        only_portuguese = parse(active(title={'pt_BR': 'Olá'}, message={'pt_BR': 'a'}))
        self.assertEqual(only_portuguese.localized(['de'])[0], 'Olá')

    def test_invalid_content_is_rejected(self):
        cases = {
            'id vazio': active(id=''), 'id com maiúscula': active(id='Boas'), 'id reservado': active(id='github'),
            'id com barra': active(id='a/b'), 'versão zero': active(version=0), 'versão texto': active(version='1'),
            'versão booleana': active(version=True), 'versão decimal': active(version=1.5),
            'sem pt_BR': active(title={'en': 'News'}, message={'en': 'Text'}),
            'mensagem sem título': active(message={'pt_BR': 'a', 'ja': 'b'}),
            'título vazio': active(title={'pt_BR': '   '}), 'título longo': active(title={'pt_BR': 'x' * 151}),
            'título com quebra': active(title={'pt_BR': 'a\nb'}), 'controle': active(message={'pt_BR': 'a\x1bb'}),
            'mensagem longa': active(message={'pt_BR': 'x' * 2001}), 'idioma inválido': active(title={'pt_BR': 'a', 'PT': 'b'}),
            'pacote repetido': active(packages=['a1', 'a1']), 'pacote URL': active(packages=['https://x/y']),
            'pacote ..': active(packages=['..']), 'pacotes demais': active(packages=[f'p{i}' for i in range(21)]),
            'filtro desconhecido': active(applies_to={'kernel': ['6']}), 'filtro vazio': active(applies_to={'version_id': []}),
            'sem id': {k: v for k, v in active().items() if k != 'id'}, 'campo extra': active(script='rm -rf /'),
        }
        for name, value in cases.items():
            with self.subTest(name), self.assertRaises(CatalogError):
                parse(value)

    def test_strict_json_size_and_encoding(self):
        for raw in (b'{', b'{"schema": 1, "enabled": true, "enabled": false}', b'{"schema": NaN, "enabled": false}',
                    b'\xff\xfe{}', b'{"schema": 1, "enabled": false}' + b' ' * announcements.MAX_BYTES):
            with self.subTest(raw=raw[:40]), self.assertRaises(CatalogError):
                announcements.parse(raw)

    def test_only_official_https_urls(self):
        for url in ('https://github.com/mainuan/atualizador-de-recursos/releases', 'https://mainuan.github.io/',
                    'https://mainuan.github.io/novidades/'):
            with self.subTest(url=url):
                self.assertEqual(parse(active(url=url)).url, url)
        for url in ('http://mainuan.github.io/', 'https://github.com/outra-conta/repo', 'https://mainuan.github.io.evil.com/',
                    'https://evil.github.io/', 'https://github.com/mainuan/../evil', 'https://github.com/mainuan/x#y',
                    'https://user@github.com/mainuan/x', 'javascript:alert(1)', 'file:///etc/passwd', ' https://github.com/mainuan/'):
            with self.subTest(url=url), self.assertRaises(CatalogError):
                parse(active(url=url))


class ChannelTests(unittest.TestCase):
    """Canal + janela, com o GitHub e o sistema simulados."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state = State(self.directory / 'state.json')
        self.fixture = Fixture()
        self.channel = github.GitHubChannel(self.directory, self.state)
        self.preferences = Preferences(self.directory / 'config' / 'preferences.json')
        for target, value in (('github_channel.system_identity', SYSTEM), ('gui.system_identity', SYSTEM),
                              ('github_channel.session_kind', SessionKind.INSTALLED)):
            p = patch('mainuan_recursos.' + target, return_value=value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(github, 'metadata', side_effect=self.fixture.metadata)
        self.metadata = p.start(); self.addCleanup(p.stop)
        p = patch('apt.Cache', return_value={})
        p.start(); self.addCleanup(p.stop)

    def automatic(self):
        """Uma verificação do autostart; devolve (janela, apresentou?, encerrou?)."""
        window = Window(self.state, self.directory, automatic=True, github_channel=self.channel,
                        preferences=self.preferences)
        self.addCleanup(window.deleteLater)
        idle = []
        window.idle.connect(lambda: idle.append(True))
        window.reload()
        wait_until(lambda: window.worker is None)
        shown = window.isVisible()
        window.close()
        return window, shown, bool(idle)

    def assert_silent(self):
        window, shown, idle = self.automatic()
        self.assertFalse(shown)
        self.assertTrue(idle)
        return window

    def test_no_announcement_published(self):
        self.fixture.announcement = None
        window = self.assert_silent()
        self.assertIsNone(self.channel.active)
        self.assertEqual(window.catalog.releases, ())
        # Releases de programas nem são consultadas sem anúncio.
        self.assertFalse(any('/repos/mainuan/programa-um' in url for url in self.fixture.calls))
        self.assertFalse(any(url.endswith('.txt') for url in self.fixture.calls))

    def test_disabled_announcement(self):
        self.fixture.announcement['enabled'] = False
        self.assert_silent()
        self.assertEqual(self.state.data['releases'], {})

    def test_active_announcement_is_shown_once(self):
        window, shown, idle = self.automatic()
        self.assertTrue(shown)
        self.assertFalse(idle)
        self.assertEqual(window.summary.text(), self.fixture.message)
        entry = self.state.entry(window.current)
        self.assertEqual(entry['presentation'], 'viewed')
        self.assertGreater(entry['presented_at'], 0)
        # Já lido: próximas verificações ficam em silêncio.
        self.assert_silent()
        self.assert_silent()

    def test_closing_counts_as_read_and_postpone_waits_24_hours(self):
        window, shown, _ = self.automatic()
        self.assertTrue(shown)
        self.state.postpone(window.current, now=1000)
        with patch('mainuan_recursos.state.time.time', return_value=1000 + 3600):
            self.assert_silent()
        with patch('mainuan_recursos.state.time.time', return_value=1000 + 86400):
            window, shown, _ = self.automatic()
        self.assertTrue(shown)

    def test_new_version_is_shown_again_and_old_stays_in_history(self):
        self.assertTrue(self.automatic()[1])
        self.fixture.announcement['version'] = 2
        window, shown, _ = self.automatic()
        self.assertTrue(shown)
        self.assertEqual(window.current.key, 'novidades-teste@2')
        self.assertEqual(window.history.count(), 2)

    def test_disabling_stops_the_popup_but_keeps_history(self):
        self.fixture.announcement['enabled'] = False
        self.fixture.announcement['version'] = 1
        self.assert_silent()
        self.fixture.announcement['enabled'] = True
        self.automatic()
        self.fixture.announcement['enabled'] = False
        self.state.data['releases'].clear()  # nem mesmo um anúncio "não lido" volta sozinho
        window = self.assert_silent()
        self.assertEqual(len(window.catalog.releases), 1)
        manual = Window(self.state, self.directory, github_channel=self.channel, preferences=self.preferences)
        self.addCleanup(manual.deleteLater)
        manual.show()
        manual.reload()
        wait_until(lambda: manual.worker is None)
        self.assertIsNone(manual.current)
        self.assertEqual(manual.summary.text().splitlines()[0], 'Nenhuma novidade publicada.')
        self.assertIn('histórico', manual.status.text())
        self.assertEqual(manual.history.count(), 1)
        manual.close()

    def test_unseen_cached_announcement_is_not_shown_offline(self):
        self.channel.load()
        for error in (URLError('sem rede'), OSError('sem rede'),
                      HTTPError(github.API, 503, 'Service Unavailable', {}, None),
                      HTTPError(github.API, 403, 'rate limit', {}, None)):
            with self.subTest(error=error), patch.object(github, 'metadata', side_effect=error):
                window = self.assert_silent()
                self.assertFalse(window.online)
                self.assertTrue(self.state.due(window.catalog.releases[0]))

    def test_github_unavailable_without_cache_or_404_on_the_api(self):
        self.fixture.overrides[github.API + github.OFFICIAL + '/commits/main'] = HTTPError(github.API, 404, 'Not Found', {}, None)
        window = self.assert_silent()
        self.assertIn('Não foi possível verificar', window.status.text())

    def test_invalid_file_too_big_or_unofficial_url_is_silent(self):
        url = f'https://raw.githubusercontent.com/mainuan/{github.OFFICIAL}/{self.fixture.commit}/announcements.json'
        for raw in (b'{"schema": 1, "enabled": true,', b'{"schema": 1, "enabled": true}',
                    json.dumps(active(url='https://example.com/')).encode(),
                    CatalogError('announcements.json excede o tamanho permitido.')):
            with self.subTest(raw=str(raw)[:50]):
                self.fixture.overrides[url] = raw
                self.assert_silent()
                self.assertEqual(self.state.data['releases'], {})

    def test_too_big_file_is_rejected_by_the_download_limit(self):
        calls = []
        def metadata(url, limit=1024 * 1024):
            calls.append((url, limit))
            return self.fixture.metadata(url, limit)
        with patch.object(github, 'metadata', side_effect=metadata):
            self.channel.load()
        self.assertIn(announcements.MAX_BYTES, [limit for url, limit in calls if url.endswith('/announcements.json')])

    def test_not_applicable_to_this_version(self):
        self.fixture.announcement['applies_to'] = {'version_id': ['2027.1']}
        self.assert_silent()
        self.fixture.announcement['applies_to'] = {'version_id': ['26.04', '2027.1'], 'architecture': ['amd64']}
        self.assertTrue(self.automatic()[1])

    def test_informative_announcement_without_packages(self):
        self.fixture.names = ()
        window, shown, _ = self.automatic()
        self.assertTrue(shown)
        self.assertEqual(window.current.packages, ())
        self.assertFalse(window.install.isVisibleTo(window))
        self.assertFalse(window.know.isVisibleTo(window))
        self.assertFalse(any('/repos/mainuan/programa' in url for url in self.fixture.calls))

    def test_translated_announcement_in_the_window(self):
        self.fixture.announcement['title']['en'] = 'Hello!'
        self.fixture.announcement['message']['en'] = 'See what is new:'
        with patch.dict(os.environ, {'LANGUAGE': 'en_US', 'LANG': 'en_US.UTF-8', 'LC_ALL': '', 'LC_MESSAGES': ''}):
            window, shown, _ = self.automatic()
        self.assertTrue(shown)
        self.assertEqual(window.summary.text(), 'Hello!\n\nSee what is new:')

    def test_preference_off_blocks_the_popup(self):
        self.preferences.set_automatic(False)
        self.assertFalse(Preferences(self.preferences.path).automatic)
        self.assert_silent()
        self.preferences.set_automatic(True)
        self.assertTrue(self.automatic()[1])

    def test_legacy_edition_from_022_cache_is_history_only(self):
        self.fixture.announcement = None
        legacy = {'release': {'id': 'github', 'version': 'f' * 24, 'title': 'x', 'summary': 'Olá! O Mainuan tem novidades.',
                              'article_url': 'https://github.com/mainuan/mainuan-gestao-drivers/releases/tag/v1.0',
                              'features': [], 'compatibility': {}}, 'assets': []}
        self.channel.cache_path.write_text(json.dumps({'schema': 1, 'sequence': 1, 'digest': 'e' * 64, 'editions': [legacy],
                                                       'pins': {}, 'repositories': {}}))
        self.state.data.update(sequence=1, digest='e' * 64)
        channel = github.GitHubChannel(self.directory, self.state)
        self.channel = channel
        window = self.assert_silent()
        self.assertEqual([r.key for r in window.catalog.releases], ['github@' + 'f' * 24])
        self.assertTrue(self.state.due(window.catalog.releases[0]))
        self.assertEqual(json.loads(channel.cache_path.read_text())['schema'], 2)


class EntryTests(unittest.TestCase):
    def test_live_session_never_queries_even_with_announcement(self):
        with patch('mainuan_recursos.application.session_kind', return_value=SessionKind.LIVE), \
             patch('mainuan_recursos.application.QApplication') as app, \
             patch('mainuan_recursos.github_channel.metadata') as metadata:
            self.assertEqual(main(['--check']), 0)
        app.assert_not_called()
        metadata.assert_not_called()

    def test_preference_off_exits_before_qt_and_network(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp, 'XDG_STATE_HOME': tmp}), \
             patch('mainuan_recursos.application.session_kind', return_value=SessionKind.INSTALLED), \
             patch('mainuan_recursos.application.QApplication') as app, \
             patch('mainuan_recursos.github_channel.metadata') as metadata:
            Preferences().set_automatic(False)
            self.assertEqual(main(['--check']), 0)
        app.assert_not_called()
        metadata.assert_not_called()

    def test_autostart_process_exits_by_itself_without_announcement(self):
        driver = '''
import sys
from unittest.mock import patch
from PyQt6.QtCore import QTimer
from test_github_channel import Fixture, SYSTEM
from mainuan_recursos import application
from mainuan_recursos.session import SessionKind
from mainuan_recursos.gui import Window
fixture = Fixture()
fixture.announcement = None if sys.argv[1] == 'none' else {**fixture.announcement, 'enabled': False}
shown = []
original_show = Window.show
original_single = QTimer.singleShot
def show(self):
    shown.append(True)
    original_show(self)
with patch.object(application, 'session_kind', return_value=SessionKind.INSTALLED), \\
     patch('mainuan_recursos.github_channel.system_identity', return_value=SYSTEM), \\
     patch('mainuan_recursos.gui.system_identity', return_value=SYSTEM), \\
     patch('mainuan_recursos.github_channel.metadata', side_effect=fixture.metadata), \\
     patch('apt.Cache', side_effect=AssertionError('APT sem anúncio')), \\
     patch.object(Window, 'show', show), \\
     patch.object(QTimer, 'singleShot', side_effect=lambda ms, callback: original_single(0 if ms == 60000 else ms, callback)):
    result = application.main(['--check'])
print('SAIU', result, len(shown), flush=True)
'''
        for scenario in ('none', 'disabled'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(prefix='mr-') as tmp:
                env = {**os.environ, 'PYTHONPATH': os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'tests'))),
                       'QT_QPA_PLATFORM': 'offscreen', 'XDG_STATE_HOME': tmp, 'XDG_CONFIG_HOME': tmp}
                result = subprocess.run([sys.executable, '-c', driver, scenario], capture_output=True, text=True,
                                        env=env, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('SAIU 0 0', result.stdout)


class RepositoryFilesTests(unittest.TestCase):
    def test_legacy_files_keep_old_clients_silent(self):
        # Clientes 0.2.2–0.3.1 leem packages.txt/message.txt: sem repositórios
        # não há edição nova; message.txt vazio faria essas versões mostrarem erro.
        lines = (ROOT / 'packages.txt').read_text(encoding='utf-8').splitlines()
        self.assertEqual([line.split('#', 1)[0].strip() for line in lines if line.split('#', 1)[0].strip()], [])
        self.assertLessEqual(len((ROOT / 'packages.txt').read_bytes()), 8192)
        self.assertTrue((ROOT / 'message.txt').read_text(encoding='utf-8').strip())


if __name__ == '__main__':
    unittest.main()
