"""Compile the gettext catalogs for the test run and select pt_BR.

Most tests assert the Brazilian Portuguese interface (the original wording),
so the test process runs with LANGUAGE=pt_BR and catalogs compiled from po/.
Language-specific behaviour (English fallback etc.) is tested explicitly in
test_localization.py with subprocesses and their own environment.
"""
import atexit
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PO = ROOT / 'po'
DOMAIN = 'mainuan-atualizador-recursos'


def compile_catalogs(destination):
    destination = Path(destination)
    languages = [line.strip() for line in (PO / 'LINGUAS').read_text().splitlines()
                 if line.strip() and not line.startswith('#')]
    if not languages:
        raise RuntimeError('po/LINGUAS lists no language')
    for language in languages:
        target = destination / language / 'LC_MESSAGES'
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(['msgfmt', '--check', '-o', str(target / f'{DOMAIN}.mo'), str(PO / f'{language}.po')],
                       check=True)
    return destination


if not os.environ.get('MAINUAN_RECURSOS_LOCALEDIR'):
    LOCALEDIR = tempfile.mkdtemp(prefix='mainuan-recursos-locale-')
    atexit.register(shutil.rmtree, LOCALEDIR, True)
    compile_catalogs(LOCALEDIR)
    os.environ['MAINUAN_RECURSOS_LOCALEDIR'] = LOCALEDIR
else:
    LOCALEDIR = os.environ['MAINUAN_RECURSOS_LOCALEDIR']
os.environ['LANGUAGE'] = 'pt_BR'

from mainuan_recursos import i18n  # noqa: E402

i18n.reload()
