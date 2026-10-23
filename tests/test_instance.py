"""Processos reais, socket local e lock; sem rede ou consulta APT."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

DRIVER = '''
from pathlib import Path
from unittest.mock import patch
from mainuan_recursos.application import main
from mainuan_recursos.gui import Window
import os, sys
log=Path(os.environ['INSTANCE_LOG'])
def record(value):
    with log.open('a') as output: output.write(value+'\\n')
original_init=Window.__init__
original_show=Window.show
def initialize(self,*args,**kwargs):
    record('constructed')
    original_init(self,*args,**kwargs)
def show(self):
    record('show')
    original_show(self)
with patch.object(Window,'__init__',initialize), patch.object(Window,'show',show), patch.object(Window,'reload',lambda self:record('reload')):
    raise SystemExit(main(sys.argv[1:]))
'''


class InstanceTests(unittest.TestCase):
    def test_single_instance_fragmented_activation_refresh_and_dead_process_recovery(self):
        with tempfile.TemporaryDirectory(prefix='mr-') as temporary:
            root=Path(temporary)
            env=os.environ.copy()
            env.update(XDG_STATE_HOME=str(root),QT_QPA_PLATFORM='offscreen',INSTANCE_LOG=str(root/'calls'))
            arguments=[sys.executable,'-c',DRIVER]
            processes=[]
            def launch():
                process=subprocess.Popen(arguments+['--check'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                processes.append(process)
                return process
            def wait_for(predicate):
                until=time.monotonic()+5
                while not predicate():
                    if time.monotonic()>until:
                        self.fail('Tempo limite no teste de instância')
                    time.sleep(.01)
            def calls():
                return (root/'calls').read_text().splitlines() if (root/'calls').exists() else []
            try:
                first=launch()
                endpoint=root/'mainuan-recursos/session.socket'
                wait_for(endpoint.exists)
                duplicate=subprocess.run(arguments+['--check'],env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(duplicate.returncode,0)
                self.assertEqual(calls().count('constructed'),1)
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(str(endpoint));client.sendall(b'sh')
                    time.sleep(.03);client.sendall(b'ow')
                wait_for(lambda:calls().count('reload')==1)
                manual=subprocess.run(arguments,env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(manual.returncode,0)
                wait_for(lambda:calls().count('reload')==2)
                self.assertEqual(calls().count('constructed'),1)
                self.assertIsNone(first.poll())
                first.terminate();first.wait(timeout=5)
                resumed=launch()
                wait_for(lambda:calls().count('constructed')==2)
                time.sleep(.1)
                self.assertIsNone(resumed.poll())
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                    process.communicate(timeout=5)

    def test_autostart_preserves_checks_when_manual_instance_started_first(self):
        driver=DRIVER.replace("    raise SystemExit(main(sys.argv[1:]))", """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    original_exec=QApplication.exec
    def execute(app):
        def close_after_promotion():
            windows=[w for w in app.topLevelWidgets() if isinstance(w,Window)]
            if windows and windows[0].automatic:
                window=windows[0]
                assert window.timer.isActive()
                window.close()
                assert not window.isVisible()
                record('background-after-close')
                timer.stop()
        timer=QTimer()
        timer.timeout.connect(close_after_promotion)
        timer.start(10)
        return original_exec()
    QApplication.exec=execute
    raise SystemExit(main(sys.argv[1:]))
""")
        with tempfile.TemporaryDirectory(prefix='mr-') as temporary:
            root=Path(temporary)
            env=os.environ.copy()
            env.update(XDG_STATE_HOME=str(root),QT_QPA_PLATFORM='offscreen',INSTANCE_LOG=str(root/'calls'))
            process=subprocess.Popen([sys.executable,'-c',driver],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                until=time.monotonic()+5
                while not (root/'mainuan-recursos/session.socket').exists():
                    if time.monotonic()>until:
                        self.fail('Instância manual não iniciou')
                    time.sleep(.01)
                result=subprocess.run([sys.executable,'-c',DRIVER,'--check'],env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,0)
                while 'background-after-close' not in (root/'calls').read_text():
                    if time.monotonic()>until:
                        self.fail('Autostart não preservou a instância manual')
                    time.sleep(.01)
                self.assertIsNone(process.poll())
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=5)
