"""Casper/Live: evidências de boot, mídia isolada e detecção inconclusiva."""
from pathlib import Path
import unittest
from unittest.mock import patch

from mainuan_recursos.application import main
from mainuan_recursos.session import SessionKind, session_kind


class LiveEnvironmentTests(unittest.TestCase):
    def detect(self, cmdline, mounts, paths=()):
        def read(path):
            value = cmdline if str(path) == '/proc/cmdline' else mounts
            if isinstance(value, Exception):
                raise value
            return value
        with patch.object(Path, 'read_text', read), patch.object(Path, 'exists', lambda path:str(path) in paths):
            return session_kind()

    def test_mounted_iso_does_not_make_normal_installation_live(self):
        mounts = '1 0 8:1 / / rw - ext4 /dev/sda1 rw\n2 1 7:0 / /cdrom ro - iso9660 /dev/loop0 ro'
        self.assertEqual(self.detect('root=UUID=teste quiet', mounts, ('/cdrom/casper',)), SessionKind.INSTALLED)

    def test_overlay_with_casper_runtime_is_live(self):
        mounts = '1 0 0:1 / / rw - overlay overlay rw'
        self.assertEqual(self.detect('quiet', mounts, ('/run/casper',)), SessionKind.LIVE)

    def test_live_root_with_unreadable_cmdline_is_live(self):
        mounts = '1 0 0:1 / / rw - overlay overlay rw\n2 1 7:0 / /rofs ro - squashfs /dev/loop0 ro'
        self.assertEqual(self.detect(OSError('sem acesso'), mounts), SessionKind.LIVE)

    def test_unknown_is_not_called_live_or_allowed_to_query(self):
        self.assertEqual(self.detect(OSError(), OSError()), SessionKind.UNKNOWN)

    def test_normal_root_with_unreadable_cmdline_is_still_installed(self):
        mounts = '1 0 8:1 / / rw - ext4 /dev/sda1 rw'
        self.assertEqual(self.detect(OSError(), mounts), SessionKind.INSTALLED)

    def test_non_live_container_overlay_is_not_classified_live(self):
        mounts = '1 0 0:1 / / rw - overlay overlay rw'
        self.assertEqual(self.detect('root=UUID=teste quiet', mounts), SessionKind.INSTALLED)

    def test_malformed_mountinfo_is_unknown(self):
        self.assertEqual(self.detect('quiet', 'inválido'), SessionKind.UNKNOWN)

    def test_manual_live_and_unknown_do_not_construct_window(self):
        for kind in (SessionKind.LIVE, SessionKind.UNKNOWN):
            with patch('mainuan_recursos.application.session_kind', return_value=kind), \
                 patch('mainuan_recursos.application.QApplication'), \
                 patch('mainuan_recursos.application.install_pt_br'), \
                 patch('mainuan_recursos.application.QMessageBox.information') as information, \
                 patch('mainuan_recursos.application.Window') as window:
                self.assertEqual(main([]), 0)
                information.assert_called_once()
                window.assert_not_called()
