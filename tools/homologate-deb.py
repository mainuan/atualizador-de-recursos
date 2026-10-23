#!/usr/bin/python3
"""Ciclo Debian em raiz descartável; host somente leitura via bubblewrap."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    opts=parser.parse_args()
    package=opts.package.resolve()
    opts.output.mkdir(parents=True,exist_ok=True)
    # O roteiro mínimo não disponibiliza shell no chroot; rejeita scripts.
    control=subprocess.run(['dpkg-deb','--ctrl-tarfile',str(package)],capture_output=True,check=True).stdout
    import io
    with tarfile.open(fileobj=io.BytesIO(control)) as archive:
        if any(Path(item.name).name in ('preinst','postinst','prerm','postrm') for item in archive):
            raise SystemExit('Este roteiro não homologa pacotes com scripts de mantenedor; use uma VM.')
    report={'scope':'Ciclo dpkg isolado; dependências copiadas apenas como metadados. Não substitui uma VM.',
            'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'steps':[]}
    logs=[]
    with tempfile.TemporaryDirectory(prefix='mainuan-deb-') as temporary:
        root=Path(temporary)
        admin=root/'var/lib/dpkg'
        admin.mkdir(parents=True)
        (admin/'updates').mkdir()
        (root/'var/log').mkdir(parents=True)
        status=Path('/var/lib/dpkg/status').read_text()
        status='\n\n'.join(part for part in status.split('\n\n')
                           if not part.startswith('Package: mainuan-atualizador-recursos\n'))+'\n'
        (admin/'status').write_text(status)
        home_state=root/'home/teste/.local/state/mainuan-recursos/state.json'
        home_state.parent.mkdir(parents=True)
        home_state.write_text('{"teste":"preservar histórico"}')
        def run(command,label,hide_development=False):
            sandbox=['bwrap','--unshare-user','--uid','0','--gid','0','--unshare-pid','--unshare-net',
                     '--ro-bind','/','/','--bind',str(root),str(root),'--proc','/proc','--dev','/dev']
            if hide_development:
                sandbox += ['--tmpfs',str(Path(__file__).resolve().parents[1]),'--chdir',str(root)]
                if Path('/usr/lib/mainuan-atualizador-recursos').exists():
                    sandbox += ['--tmpfs','/usr/lib/mainuan-atualizador-recursos']
            result=subprocess.run(sandbox+command,capture_output=True,text=True,timeout=30)
            logs.append(f'[{label}] código {result.returncode}\n{result.stdout}{result.stderr}')
            if result.returncode:
                raise RuntimeError(logs[-1])
            report['steps'].append(label)
            return result.stdout
        dpkg=['dpkg','--root='+str(root),'--admindir='+str(admin),'--log='+str(root/'var/log/dpkg.log'),'--no-triggers']
        run(dpkg+['--install',str(package)],'instalação na raiz descartável')
        launcher=root/'usr/bin/mainuan-atualizador-recursos'
        desktop=root/'usr/share/applications/org.mainuan.Recursos.desktop'
        autostart=root/'etc/xdg/autostart/mainuan-recursos.desktop'
        icon=root/'usr/share/icons/hicolor/scalable/apps/mainuan-recursos.svg'
        assert launcher.exists() and os.access(launcher,os.X_OK)
        assert 'Exec=mainuan-atualizador-recursos\n' in desktop.read_text()
        assert 'Exec=mainuan-atualizador-recursos --check\n' in autostart.read_text()
        assert 'OnlyShowIn=KDE;' in autostart.read_text()
        assert icon.exists()
        illustration=root/'usr/lib/mainuan-atualizador-recursos/mainuan_recursos/assets/mainuan-novidades.png'
        assert illustration.is_file()
        report['illustration_sha256']=hashlib.sha256(illustration.read_bytes()).hexdigest()
        run(['desktop-file-validate',str(desktop),str(autostart)],'entradas desktop instaladas válidas')
        env=['env','PYTHONDONTWRITEBYTECODE=1','QT_QPA_PLATFORM=offscreen',
             'PYTHONPATH='+str(root/'usr/lib/mainuan-atualizador-recursos')]
        version=run(env+['/usr/bin/python3',str(launcher),'--version'],'entrada manual instalada --version',True)
        report['version']=version.strip()
        demo_probe = """
import runpy,sys,time
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QPushButton
original=QApplication.exec
stage=['start']
progress_seen=[]
def execute(app):
    def tick():
        modal=app.activeModalWidget()
        if isinstance(modal,QDialog):
            if stage[0]=='cancel':
                next(button for button in modal.findChildren(QPushButton) if button.text()=='Cancelar').click()
                stage[0]='cancelled'
            else:
                next(button for button in modal.findChildren(QPushButton) if button.text()=='Instalar novidades').click()
            return
        windows=[w for w in app.topLevelWidgets() if hasattr(w,'demo')]
        if not windows or windows[0].worker:
            return
        window=windows[0]
        if stage[0]=='start':
            import mainuan_recursos.gui as gui
            from mainuan_recursos.classic import ClassicContent,ILLUSTRATION
            assert Path(gui.__file__).is_relative_to(Path(INSTALLED_LIB))
            assert ILLUSTRATION.is_relative_to(Path(INSTALLED_LIB)) and ILLUSTRATION.is_file()
            assert not Path(SOURCE_CHECKOUT,'tools').exists()
            assert isinstance(window.view,ClassicContent) and window.illustration.pixmap.hasAlphaChannel()
            assert window.demo and len(window.current.packages)==3
            assert window.summary.text()==window.current.summary
            assert [item.text() for item in window.program_labels]==['•  '+feature.title for feature in window.current.features]
            assert window.state.entry(window.current)['packages']=='pending'
            articles=[]
            QDesktopServices.openUrl=staticmethod(lambda url:articles.append(url.toString()) or True)
            window.know.click()
            assert articles==[window.current.article_url]
            window.history_action.trigger()
            assert window.history_dialog.isVisible() and window.history.count()==2
            close=window.history_dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
            assert close.text().replace('&','')=='Fechar'
            close.click()
            window.details_action.trigger()
            assert window.current.packages[0].name in window.details_text.toPlainText()
            close=window.details_dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
            assert close.text().replace('&','')=='Fechar'
            close.click()
            assert window.grab().save(SCREENSHOT)
            stage[0]='cancel'
            window.install.click()
        elif stage[0]=='cancelled':
            assert not window.demo.installed and window.state.entry(window.current)['packages']=='pending'
            assert 'cancelada' in window.status.text()
            stage[0]='installing'
            window.install.click()
        elif window.controller.busy and window.progress.maximum()==100 and window.progress.value()>0:
            progress_seen.append(True)
        elif window.demo.installed and not window.controller.busy:
            assert window.state.entry(window.current)['packages']=='installed'
            assert progress_seen and not window.install.isEnabled()
            timer.stop()
            before=time.time()
            window.later.click()
            assert before+86400<=window.state.entry(window.current)['postponed_until']<=time.time()+86400
            print('Aplicativo instalado: beija-flor, catálogo, menus, português, artigo, cancelamento, progresso, conclusão e adiamento verificados; checkout oculto')
            app.quit()
    timer=QTimer()
    timer.timeout.connect(tick)
    timer.start(30)
    QTimer.singleShot(10000,lambda:app.exit(1))
    return original()
QApplication.exec=execute
sys.argv=[LAUNCHER,'--demo']
runpy.run_path(LAUNCHER,run_name='__main__')
""".replace('LAUNCHER',repr(str(launcher))).replace('INSTALLED_LIB',repr(str(root/'usr/lib/mainuan-atualizador-recursos'))).replace('SOURCE_CHECKOUT',repr(str(Path(__file__).resolve().parents[1]))).replace('SCREENSHOT',repr(str(root/'demo-instalado.png')))
        run(env+['/usr/bin/python3','-c',demo_probe],'demo do aplicativo instalado: fluxo completo sem checkout',True)
        shutil.copyfile(root/'demo-instalado.png',opts.output/'demo-instalado.png')
        report['installed_classic_ui']=True
        report['development_hidden_during_demo']=True
        probe=('from PyQt6.QtWidgets import QApplication; from PyQt6.QtGui import QIcon; '
               f'app=QApplication([]); icon=QIcon({str(icon)!r}); '
               'assert not icon.pixmap(48,48).isNull(); print("Ícone SVG renderizado")')
        run(env+['/usr/bin/python3','-c',probe],'ícone instalado renderizado por Qt')
        config=root/'etc/mainuan/atualizador-recursos.json'
        original=json.loads(config.read_text())
        assert original['keys']=={}
        changed=config.read_bytes()+b'\n'
        config.write_bytes(changed)
        run(dpkg+['--remove','mainuan-atualizador-recursos'],'remoção')
        assert not launcher.exists()
        assert config.read_bytes()==changed and home_state.exists()
        run(dpkg+['--install',str(package)],'reinstalação')
        assert launcher.exists() and config.read_bytes()==changed and home_state.exists()
        report['configuration_preserved']=True
        report['user_state_preserved']=True
        report['production_disabled']=json.loads(config.read_text())['keys']=={}
    report['success']=True
    (opts.output/'resultado-deb.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (opts.output/'dpkg.log').write_text('\n'.join(logs))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
