#!/usr/bin/python3
"""Observa o timer real do launcher extraído, com produção sem chave e rede bloqueada."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

DRIVER=r'''
import json,os,runpy,sys,time
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from mainuan_recursos.catalog import Config
from mainuan_recursos.gui import Window
original_exec=QApplication.exec
original_reload=Window.reload
original_load=Config.load
started=time.monotonic()
checks=[]
report={'scope':'Timer real do launcher extraído; configuração sem chave; rede bloqueada.', 'automatic_checks':checks}
def reload(self):
    checks.append(round(time.monotonic()-started,3))
    original_reload(self)
def execute(app):
    def inspect():
        windows=[w for w in app.topLevelWidgets() if isinstance(w,Window)]
        if windows:
            window=windows[0]
            report['hourly_interval_ms']=window.timer.interval()
            report['shown_before_check']=window.isVisible()
            if checks and window.worker is None:
                report['status']=window.status.text()
                report['production_disabled']='chave pública' in report['status']
                report['visible']=window.isVisible()
                finish()
        if time.monotonic()-started>75:
            report['error']='Tempo limite';finish()
    def finish():
        timer.stop()
        Path(os.environ['PROBE_REPORT']).write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False),flush=True)
        app.quit()
    timer=QTimer();timer.timeout.connect(inspect);timer.start(200)
    return original_exec()
QApplication.exec=execute
Window.reload=reload
with patch('mainuan_recursos.gui.Config.load',side_effect=lambda:original_load(Path(os.environ['PROBE_CONFIG']))),patch('mainuan_recursos.catalog.download',side_effect=AssertionError('Rede bloqueada')):
    sys.argv=[os.environ['PROBE_LAUNCHER'],'--check']
    runpy.run_path(sys.argv[0],run_name='__main__')
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    opts=parser.parse_args()
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mainuan-autostart-') as tmp:
        root=Path(tmp)
        subprocess.run(['dpkg-deb','--extract',str(opts.package.resolve()),str(root)],check=True)
        env=os.environ.copy()
        env.update(PYTHONPATH=str(root/'usr/lib/mainuan-atualizador-recursos'),
                   PYTHONDONTWRITEBYTECODE='1',XDG_STATE_HOME=str(root/'state'),
                   PROBE_LAUNCHER=str(root/'usr/bin/mainuan-atualizador-recursos'),
                   PROBE_CONFIG=str(root/'etc/mainuan/atualizador-recursos.json'),PROBE_REPORT=str(opts.output.resolve()))
        subprocess.run(['/usr/bin/python3','-c',DRIVER],env=env,check=True,timeout=80)
    report=json.loads(opts.output.read_text())
    return 0 if len(report['automatic_checks'])==1 and not report.get('visible') and report.get('production_disabled') else 1


if __name__=='__main__':
    raise SystemExit(main())
