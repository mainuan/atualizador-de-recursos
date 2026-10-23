"""Identificadores simulados; não representam uma ISO Mainuan 2027.1 já testada."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mainuan_recursos.application import main
from mainuan_recursos.catalog import CatalogError
from mainuan_recursos.github_channel import GitHubChannel
from mainuan_recursos import github_trial
from mainuan_recursos.session import (SessionKind, base_identity, supported_system,
                                     system_compatibility, system_identity)
from mainuan_recursos.state import State
from mainuan_recursos.gui import Window
from qt_support import wait_until
from test_github_channel import Fixture


def os_release(name='Mainuan 2027.1 RC1'):
    return {'ID': 'mainuan', 'VERSION_ID': '2027.1', 'VERSION': name,
            'PRETTY_NAME': name, 'ID_LIKE': 'ubuntu debian', 'UBUNTU_CODENAME': 'resolute'}


def identity(info):
    with patch('platform.freedesktop_os_release', return_value=info), \
         patch('mainuan_recursos.session.subprocess.run', return_value=SimpleNamespace(stdout='amd64\n')):
        return system_identity()


class IdentityTests(unittest.TestCase):
    def test_current_and_legacy_identifiers_remain_supported(self):
        for distro, version in (('ubuntu','26.04'), ('ubuntu','2026'), ('mainuan','26.04'), ('mainuan','2026')):
            with self.subTest(distro=distro, version=version):
                system = identity({'ID':distro,'VERSION_ID':version,'UBUNTU_CODENAME':'resolute'})
                self.assertTrue(supported_system(system))
                self.assertEqual((system['base_id'],system['base_version_id']),('ubuntu','26.04'))
                self.assertEqual(system['version_id'],version)

    def test_mainuan_rc1_and_final_keep_commercial_and_base_versions_distinct(self):
        for presentation in ('Mainuan 2027.1 RC1', 'Mainuan 2027.1'):
            with self.subTest(presentation=presentation):
                system = identity(os_release(presentation))
                self.assertEqual(system['distro_id'],'mainuan')
                self.assertEqual(system['version_id'],'2027.1')
                self.assertEqual(system['base_version_id'],'26.04')
                self.assertTrue(supported_system(system))

    def test_expected_mainuan_identifiers_are_accepted_without_presentation_fields(self):
        self.assertTrue(supported_system(identity({'ID':'mainuan','VERSION_ID':'2027.1'})))

    def test_incompatible_systems_and_cartesian_product_are_rejected(self):
        for distro, version in (('ubuntu','24.04'),('ubuntu','26.10'),('ubuntu','27.04'),
                               ('ubuntu','2027.1'),('mainuan','2027.1~rc1'),('mainuan','2028.1'),
                               ('debian','26.04'),('',''),('mainuan','')):
            with self.subTest(distro=distro,version=version):
                self.assertFalse(supported_system(identity({'ID':distro,'VERSION_ID':version})))

    def test_explicit_incompatible_base_is_not_ignored(self):
        system = identity({**os_release(),'UBUNTU_CODENAME':'noble'})
        self.assertFalse(supported_system(system))
        self.assertFalse(supported_system({'distro_id':'mainuan','version_id':'2027.1','base_id':'ubuntu','base_version_id':'24.04'}))
        self.assertIsNone(base_identity({'distro_id':'mainuan','version_id':'2027.1','base_id':'debian'}))


class ChannelCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state = State(self.directory/'state.json')
        self.channel = GitHubChannel(self.directory,self.state)
        self.fixture = Fixture()
        p=patch('mainuan_recursos.github_channel.metadata', side_effect=self.fixture.metadata)
        self.metadata=p.start(); self.addCleanup(p.stop)

    def test_consultation_and_selection_for_current_rc1_and_final(self):
        for info in ({'ID':'ubuntu','VERSION_ID':'2026'},
                     {'ID':'mainuan','VERSION_ID':'26.04'},os_release(),os_release('Mainuan 2027.1')):
            system=identity(info)
            with self.subTest(info=info), patch('mainuan_recursos.github_channel.system_identity',return_value=system):
                catalog,online=self.channel.load()
                self.assertTrue(online)
                self.assertTrue(catalog.releases[0].compatible(system))
                self.assertEqual(len(catalog.releases[0].packages),1)
        self.assertFalse((self.directory/'pacotes-github').exists())

    def test_selection_uses_the_same_pair_policy_as_consultation(self):
        system=identity(os_release())
        with patch('mainuan_recursos.github_channel.system_identity',return_value=system):
            release=self.channel.load()[0].releases[0]
        self.assertTrue(release.compatible(system))
        for unsupported in ({'distro_id':'ubuntu','version_id':'2027.1','architecture':'amd64'},
                            {'distro_id':'ubuntu','version_id':'24.04','architecture':'amd64'},
                            {**system,'ubuntu_codename':'noble'}):
            self.assertFalse(release.compatible(unsupported))
        self.assertFalse(replace(release,compatibility=system_compatibility(('arm64',))).compatible(system))

    def test_normal_and_automatic_windows_offer_news_for_rc1_and_final(self):
        for presentation in ('Mainuan 2027.1 RC1','Mainuan 2027.1'):
            for automatic in (False,True):
                with self.subTest(presentation=presentation,automatic=automatic), \
                     patch('platform.freedesktop_os_release',return_value=os_release(presentation)), \
                     patch('mainuan_recursos.session.subprocess.run',return_value=SimpleNamespace(stdout='amd64\n')), \
                     patch('apt.Cache',return_value={}):
                    window=Window(State(),self.directory,automatic=automatic,github_channel=self.channel)
                    self.addCleanup(window.deleteLater)
                    if not automatic:
                        window.show()
                    window.reload()
                    wait_until(lambda:window.worker is None)
                    self.assertTrue(window.isVisible())
                    self.assertTrue(window.online)
                    self.assertTrue(window.install.isEnabled())
                    self.assertEqual(window.system['version_id'],'2027.1')
                    self.assertEqual(window.system['base_version_id'],'26.04')
                    window.close()

    def test_incompatible_environment_is_blocked_before_network_even_with_cache(self):
        with patch('mainuan_recursos.github_channel.system_identity',return_value=identity(os_release())):
            self.channel.load()
        self.metadata.reset_mock()
        with patch('mainuan_recursos.github_channel.system_identity',return_value=identity({'ID':'ubuntu','VERSION_ID':'24.04'})):
            with self.assertRaisesRegex(CatalogError,'Kubuntu 26.04'):
                self.channel.load()
        self.metadata.assert_not_called()
        self.assertFalse(self.channel.online)

    def test_offline_cache_022_keeps_history_and_accepts_2027_identifiers(self):
        with patch('mainuan_recursos.github_channel.system_identity',return_value=identity({'ID':'ubuntu','VERSION_ID':'2026'})):
            release=self.channel.load()[0].releases[0]
        self.state.postpone(release,now=1000)
        cache=json.loads(self.channel.cache_path.read_text())
        cache['editions'][0]['release']['compatibility']={'distro_id':['mainuan','ubuntu'],
             'version_id':['26.04','2026'],'architecture':['amd64']}
        self.channel.cache_path.write_text(json.dumps(cache))
        restarted=GitHubChannel(self.directory,State(self.state.path))
        with patch('mainuan_recursos.github_channel.system_identity',return_value=identity(os_release())), \
             patch('mainuan_recursos.github_channel.metadata',side_effect=OSError('Sem rede')):
            catalog,online=restarted.load()
        self.assertFalse(online)
        self.assertEqual(catalog.releases[0].key,release.key)
        self.assertTrue(catalog.releases[0].compatible(identity(os_release())))
        self.assertFalse(restarted.state.due(catalog.releases[0],now=87399))
        self.assertTrue(restarted.state.due(catalog.releases[0],now=87400))

    def test_legacy_trial_uses_the_same_supported_systems(self):
        with patch.object(github_trial.subprocess,'run',return_value=SimpleNamespace(returncode=0)), \
             patch.object(github_trial.os,'geteuid',return_value=1000), \
             patch.object(github_trial,'session_kind',return_value=SessionKind.INSTALLED), \
             patch.object(github_trial,'system_identity',return_value=identity(os_release())):
            github_trial.check_vm()


class LiveCompatibilityTests(unittest.TestCase):
    def test_mainuan_2027_live_never_consults_or_constructs_main_window(self):
        for arguments in ([],['--check']):
            with self.subTest(arguments=arguments), \
                 patch('platform.freedesktop_os_release',return_value=os_release()), \
                 patch('mainuan_recursos.application.session_kind',return_value=SessionKind.LIVE), \
                 patch('mainuan_recursos.application.QApplication'), \
                 patch('mainuan_recursos.application.install_pt_br'), \
                 patch('mainuan_recursos.application.QMessageBox.information'), \
                 patch('mainuan_recursos.application.Window') as window, \
                 patch('mainuan_recursos.github_channel.metadata') as metadata:
                self.assertEqual(main(arguments),0)
                window.assert_not_called()
                metadata.assert_not_called()
