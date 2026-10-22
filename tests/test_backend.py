import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from mainuan_recursos.backend import load_extra_packages, scan_resources


def pkg(name, installed='1.0', candidate='2.0', upgradable=True):
    return SimpleNamespace(
        name=name,
        is_installed=bool(installed),
        is_upgradable=upgradable,
        installed=SimpleNamespace(version=installed) if installed else None,
        candidate=SimpleNamespace(version=candidate, summary='Recurso de teste') if candidate else None,
    )


class BackendTests(unittest.TestCase):
    def test_restricts_updates_to_mainuan(self):
        fake_cache = [pkg('mainuan-tema'), pkg('firefox'), pkg('mainuan-static', upgradable=False)]
        with tempfile.TemporaryDirectory() as d:
            result = scan_resources(fake_cache, Path(d) / 'missing')
        self.assertEqual([p.package for p in result], ['mainuan-tema'])

    def test_allowlist_with_safe_literal_names(self):
        with tempfile.TemporaryDirectory() as d:
            conf = Path(d) / 'resources.conf'
            conf.write_text('welcome5\nfirefox # comentário\napt;rm -rf /\n', encoding='utf-8')
            self.assertEqual(load_extra_packages(conf), {'welcome5', 'firefox'})
            result = scan_resources([pkg('welcome5'), pkg('mainuan-base')], conf)
            self.assertEqual([p.package for p in result], ['mainuan-base', 'welcome5'])

    def test_does_not_include_noninstalled_or_current(self):
        fake_cache = [pkg('mainuan-new', installed=None), pkg('mainuan-old', upgradable=False)]
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(scan_resources(fake_cache, Path(d) / 'not-present'), [])


if __name__ == '__main__':
    unittest.main()
