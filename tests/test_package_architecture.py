"""Barreira de empacotamento Python puro; nenhum compilador ou instalação."""
import importlib.util
import io
from pathlib import Path
import tarfile
import unittest

spec = importlib.util.spec_from_file_location('audit_python_package', Path(__file__).resolve().parents[1] / 'tools/audit_python_package.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def archive(name, contents):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as stream:
        member = tarfile.TarInfo(name)
        member.size = len(contents)
        stream.addfile(member, io.BytesIO(contents))
    return output.getvalue()


class ArchitectureTests(unittest.TestCase):
    def test_python_launcher_is_not_native_code(self):
        self.assertEqual(audit.inspect_members(archive('usr/bin/mainuan', b'#!/usr/bin/python3\nprint(1)\n')), (1, []))

    def test_disguised_elf_is_detected_by_contents(self):
        self.assertEqual(audit.inspect_members(archive('usr/share/picture.png', b'\x7fELFpayload'))[1], ['usr/share/picture.png'])

    def test_shared_library_and_archive_are_rejected(self):
        for name, contents in [('usr/lib/libqt.so.6', b'test'), ('usr/lib/libqt.a', b'!<arch>\n')]:
            with self.subTest(name=name):
                self.assertEqual(audit.inspect_members(archive(name, contents))[1], [name])
