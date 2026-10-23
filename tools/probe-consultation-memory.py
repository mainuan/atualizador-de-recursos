#!/usr/bin/python3
"""Mede repouso e leitura APT real com catálogo local autenticado, sem instalações."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from mainuan_recursos.catalog import Config, authenticate
from mainuan_recursos.gui import Window
from mainuan_recursos.state import State


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    opts=parser.parse_args()
    config=Config.load(opts.kit/'config-homologacao.json')
    catalog=authenticate((opts.kit/'edicoes/novidades-v1.json').read_bytes(),
                         (opts.kit/'edicoes/novidades-v1.json.sig').read_bytes(),config)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    report={'platform':app.platformName(),'catalog_authenticated':True,'apt_reads_real':True,
            'remote_transport_replaced':True,'installation_requests':0,'memory_kib':[]}
    def memory(stage):
        smaps=Path('/proc/self/smaps_rollup').read_text()
        data={line.split(':')[0]:int(line.split()[1]) for line in smaps.splitlines() if line.startswith(('Rss:','Pss:'))}
        report['memory_kib'].append(dict(stage=stage,**data))
    with tempfile.TemporaryDirectory(prefix='mainuan-memoria-') as tmp:
        window=Window(State(Path(tmp)/'state.json'),Path(tmp),automatic=True)
        stage=['idle'];started=[time.monotonic()];cpu=[time.process_time()];gaps=[];last=[time.monotonic()]
        deadline=time.monotonic()+15
        memory('idle-initial')
        def finish():
            timer.stop();window.hide()
            report['vm_hwm_kib']=int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:')))
            report['max_gui_timer_gap_ms']=round(max(gaps)*1000)
            opts.output.parent.mkdir(parents=True,exist_ok=True)
            opts.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
            print(json.dumps(report,ensure_ascii=False));app.quit()
        def tick():
            now=time.monotonic();gaps.append(now-last[0]);last[0]=now
            if now>deadline:
                report['error']='Tempo limite';finish();return
            if stage[0]=='idle' and now-started[0]>=2:
                report['idle_cpu_seconds']=round(time.process_time()-cpu[0],4)
                memory('idle-after-2s')
                stage[0]='query';started[0]=now
                window.reload()
            elif stage[0]=='query':
                memory('query')
                if window.worker is None:
                    report['query_ms']=round((now-started[0])*1000)
                    report['packages_verified']=bool(window.plans) and not window.package_error
                    report['install_disabled']=not window.install.isEnabled()
                    stage[0]='after';started[0]=now;cpu[0]=time.process_time()
            elif stage[0]=='after' and now-started[0]>=2:
                memory('after-query-idle')
                report['warmup_cpu_seconds']=round(time.process_time()-cpu[0],4)
                stage[0]='stable-idle';started[0]=now;cpu[0]=time.process_time()
            elif stage[0]=='stable-idle' and now-started[0]>=5:
                memory('stable-idle-after-5s')
                report['stable_idle_seconds']=round(now-started[0],2)
                report['stable_idle_cpu_seconds']=round(time.process_time()-cpu[0],4)
                finish()
        timer=QTimer();timer.timeout.connect(tick);timer.start(100)
        # Somente o transporte de catálogo é substituído. O worker usa APT real.
        with patch('mainuan_recursos.gui.Config.load',return_value=config), \
             patch('mainuan_recursos.gui.Repository.load',return_value=(catalog,True)), \
             patch('mainuan_recursos.packagekit.QtDBus.QDBusConnection.systemBus',side_effect=AssertionError('PackageKit bloqueado neste ensaio')):
            app.exec()
    return 0 if report.get('packages_verified') and report.get('install_disabled') else 1


if __name__=='__main__':
    raise SystemExit(main())
