from pathlib import Path
from unittest.mock import mock_open, patch
import unittest

from mainuan_recursos.backend import is_live_session


class LiveTests(unittest.TestCase):
    def test_detects_casper_kernel_parameter(self):
        def exists(self):
            return False
        with patch.object(Path, 'exists', exists), patch.object(Path, 'read_text', return_value='quiet boot=casper splash'):
            self.assertTrue(is_live_session())

    def test_regular_system_not_live(self):
        with patch.object(Path, 'exists', return_value=False), patch.object(Path, 'read_text', return_value='quiet splash'):
            self.assertFalse(is_live_session())


if __name__ == '__main__':
    unittest.main()
