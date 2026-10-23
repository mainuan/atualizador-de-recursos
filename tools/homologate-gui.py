#!/usr/bin/python3
"""Captura somente as janelas do demo e mede memória; nunca instala pacotes."""
import argparse
import json
import configparser
import os
import tempfile
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.state import State
from mainuan_recursos.catalog import Config, authenticate
from mainuan_recursos.localization import install_pt_br


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--palette',choices=('active','light','dark'),default='active')
    parser.add_argument('--scheme',type=Path,help='arquivo .colors aplicado apenas ao processo de ensaio')
    parser.add_argument('--size',default='720x420')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--test-catalog', type=Path)
    parser.add_argument('--test-config', type=Path)
    opts=parser.parse_args()
    if bool(opts.test_catalog) != bool(opts.test_config):
        parser.error('Use --test-catalog e --test-config juntos; o backend permanece simulado.')
    width,height=map(int,opts.size.split('x'))
    opts.output.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    private_config=None
    expected_window=None
    if opts.scheme:
        scheme=opts.scheme.read_text()
        config=configparser.ConfigParser(interpolation=None)
        config.read_string(scheme)
        rgb=[int(c) for c in config['Colors:Window']['BackgroundNormal'].split(',')[:3]]
        expected_window='#'+''.join(f'{c:02x}' for c in rgb)
        private_config=tempfile.TemporaryDirectory(prefix='mainuan-paleta-')
        os.environ['XDG_CONFIG_HOME']=private_config.name
        scheme=scheme.replace('[General]',f'[General]\nColorScheme={opts.scheme.stem}',1)
        scheme+='\n[KDE]\nwidgetStyle=Breeze\n'
        Path(private_config.name,'kdeglobals').write_text(scheme)
    app=QApplication([])
    app.setQuitOnLastWindowClosed(False)
    install_pt_br(app)
    # Apenas a paleta deste processo de homologação. O aplicativo não fixa cores.
    if opts.palette != 'active':
        palette=QPalette()
        dark=opts.palette=='dark'
        values={'Window':'#242424' if dark else '#f5f5f5', 'WindowText':'#eeeeee' if dark else '#202020',
                'Base':'#181818' if dark else '#ffffff', 'AlternateBase':'#303030' if dark else '#e8e8e8',
                'Text':'#eeeeee' if dark else '#202020', 'Button':'#303030' if dark else '#eeeeee',
                'ButtonText':'#eeeeee' if dark else '#202020', 'Highlight':'#3579b0', 'HighlightedText':'#ffffff'}
        for role,color in values.items():
            palette.setColor(getattr(QPalette.ColorRole,role),QColor(color))
        app.setPalette(palette)
    demo=Demo()
    if opts.test_catalog:
        demo.catalog = authenticate(opts.test_catalog.read_bytes(),
            Path(str(opts.test_catalog) + '.sig').read_bytes(), Config.load(opts.test_config))
        if demo.catalog.releases:
            demo.release = demo.catalog.releases[0]
    window=Window(State(),demo=demo)
    window.resize(width,height)
    window.show();window.reload()
    report={'platform':app.platformName(),'style':app.style().objectName(),'palette':opts.palette,
            'requested_size':[width,height],'device_pixel_ratio':window.devicePixelRatioF(),'programs':3,
            'scheme_file':str(opts.scheme) if opts.scheme else None,
            'window_color':app.palette().color(QPalette.ColorRole.Window).name(),
            'scheme_matches':expected_window is None or expected_window==app.palette().color(QPalette.ColorRole.Window).name()}
    stage=['initial']
    deadline=time.monotonic()+15
    sampling=[]

    def memory():
        try:
            text=Path('/proc/self/smaps_rollup').read_text()
            return {line.split(':')[0]:int(line.split()[1]) for line in text.splitlines()
                    if line.startswith(('Rss:','Pss:'))}
        except OSError:
            return {}

    def save(name,widget=window):
        if not widget.grab().save(str(opts.output/f'{name}.png')):
            raise RuntimeError('Não foi possível salvar a captura.')
        sampling.append(memory())

    def tick():
        if time.monotonic()>deadline:
            report['error']='Tempo limite no fluxo gráfico'
            finish()
            return
        if stage[0]=='initial' and window.worker is None:
            report['ready_ms']=round((time.monotonic()-started)*1000)
            report['actual_size']=[window.width(),window.height()]
            report['frameless']=bool(window.windowFlags() & Qt.WindowType.FramelessWindowHint)
            margins=window.windowHandle().frameMargins()
            report['frame_margins']=[margins.left(),margins.top(),margins.right(),margins.bottom()]
            report['all_actions_inside']=all(window.rect().contains(button.mapTo(window,button.rect().center()))
                                            for button in (window.know,window.install,window.options,window.later))
            report['classic_view']=type(window.view).__name__=='ClassicContent'
            report['programs']=len(window.program_labels)
            report['illustration_alpha']=window.illustration.pixmap.hasAlphaChannel()
            report['program_titles']=[item.text() for item in window.program_labels]
            report['catalog_message']=window.summary.text()==window.current.summary
            report['menu_actions']=[action.text() for action in window.view.menu.actions() if not action.isSeparator()]
            save('novidade')
            stage[0]='confirmation'
            window.prepare()
        elif stage[0]=='confirmation':
            dialog=app.activeModalWidget()
            if isinstance(dialog,QDialog):
                save('confirmacao',dialog)
                approve=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Instalar novidades')
                stage[0]='installing'
                approve.click()
        elif stage[0]=='installing' and window.controller.busy and window.progress.maximum()==100:
            save('progresso');stage[0]='done'
        elif stage[0] in ('installing','done') and demo.installed and not window.controller.busy:
            save('concluido')
            report['completed']=window.state.entry(demo.release)['packages']=='installed'
            report['memory_kib']=sampling
            report['vm_hwm_kib']=int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:')))
            finish()

    def finish():
        timer.stop()
        (opts.output/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        window.hide()
        app.quit()

    timer=QTimer()
    timer.timeout.connect(tick)
    timer.start(30)
    app.exec()
    print(json.dumps(report,ensure_ascii=False))
    if private_config:
        private_config.cleanup()
    return 0 if all(report.get(key) for key in ('completed','all_actions_inside','scheme_matches',
                                               'classic_view','illustration_alpha','catalog_message')) else 1


if __name__=='__main__':
    raise SystemExit(main())
