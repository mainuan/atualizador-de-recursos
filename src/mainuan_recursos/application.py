"""Inicialização KDE/Wayland e instância única por usuário."""
import argparse
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QLockFile, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .demo import Demo, SCENARIOS
from .catalog import Config, authenticate
from .gui import Window
from .i18n import _
from .localization import install_translations
from .preferences import Preferences
from .session import SessionKind, session_kind
from .state import State, state_directory


# O QApplication vive até o fim do processo. Destruí-lo ao sair de main(),
# junto das variáveis locais e antes de janelas, servidor e threads, fazia o
# --check que encerra em silêncio cair com SIGSEGV em ~QGuiApplication.
_application = None


def main(argv=None):
    global _application
    parser = argparse.ArgumentParser(description=_('Discover and receive the official Mainuan news.'))
    parser.add_argument('--check', action='store_true', help=_('check once after login; open only for an explicitly published announcement, otherwise exit silently'))
    parser.add_argument('--homologacao-github', action='store_true', help=_('real, manual trial in a VM: GitHub packages.txt/message.txt and Driver Manager 1.0'))
    parser.add_argument('--demo', action='store_true', help=_('demonstrate the whole flow without modifying the system'))
    parser.add_argument('--scenario', choices=SCENARIOS, default='novo', help=_('demonstration scenario'))
    parser.add_argument('--test-catalog', type=Path, help=_('signed local catalog, only with --demo'))
    parser.add_argument('--test-config', type=Path, help=_('test configuration and key, only with --demo'))
    parser.add_argument('--version', action='version', version=__version__)
    opts = parser.parse_args(argv)
    if opts.homologacao_github:
        if opts.check or opts.demo or opts.test_catalog or opts.test_config:
            parser.error(_('--homologacao-github is manual and cannot be combined with --check/--demo.'))
        from .github_trial import check_vm
        try:
            check_vm()
        except Exception as exc:
            parser.exit(1, _('Acceptance test unavailable: {error}').format(error=exc) + '\n')
    if (opts.test_catalog or opts.test_config) and not (opts.demo and opts.test_catalog and opts.test_config):
        parser.error(_('Use --demo --test-catalog FILE --test-config FILE together.'))
    session = SessionKind.INSTALLED if opts.demo else session_kind()
    if session != SessionKind.INSTALLED and opts.check:
        return 0
    preferences = None if opts.demo or opts.homologacao_github else Preferences()
    if opts.check and preferences is not None and not preferences.automatic:
        # O usuário desligou as novidades automáticas: nem consulta a rede.
        return 0
    app = _application = QApplication(sys.argv[:1])
    install_translations(app)
    app.setApplicationName('mainuan-atualizador-recursos')
    app.setOrganizationName('Mainuan')
    app.setDesktopFileName('org.mainuan.Recursos')
    # Fechar a janela (inclusive a aberta pelo autostart) encerra o processo.
    app.setQuitOnLastWindowClosed(True)
    if session != SessionKind.INSTALLED:
        message = (_('Checking for news becomes available after installing Mainuan. The Live session will not be queried.')
                   if session == SessionKind.LIVE else
                   _('Could not determine the session type. Querying and installing features have been disabled.'))
        QMessageBox.information(None, _('Mainuan News'), message)
        return 0
    directory = state_directory()
    if opts.homologacao_github:
        directory = directory.with_name('mainuan-recursos-homologacao-github')
    if opts.demo:
        demo, state = Demo(opts.scenario), State()
        if opts.test_catalog:
            try:
                demo.catalog = authenticate(opts.test_catalog.read_bytes(), Path(str(opts.test_catalog) + '.sig').read_bytes(), Config.load(opts.test_config))
                if demo.catalog.releases:
                    demo.release = demo.catalog.releases[0]
            except Exception as exc:
                QMessageBox.warning(None, _('Invalid test catalog'), str(exc))
                return 1
        if opts.scenario == 'visualizado':
            for release in demo.catalog.releases:
                state.viewed(release)
        elif opts.scenario == 'adiado':
            for release in demo.catalog.releases:
                state.postpone(release)
        window = Window(state, automatic=opts.check, demo=demo)
    else:
        try:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as exc:
            if opts.check:
                print(_('Could not open the state directory: {error}').format(error=exc), file=sys.stderr)
            else:
                QMessageBox.warning(None, _('Could not open the history'), str(exc))
            return 1
        lock = QLockFile(str(directory / 'session.lock'))
        lock.setStaleLockTime(0)
        socket_path = str(directory / 'session.socket')
        if not lock.tryLock(0):
            if lock.error() != QLockFile.LockError.LockFailedError:
                print(_('Could not lock the local state. Check the directory permissions.'), file=sys.stderr)
                return 1
            client = QLocalSocket()
            client.connectToServer(socket_path)
            if client.waitForConnected(1500):
                # O autostart preserva verificações mesmo se a primeira instância
                # foi aberta manualmente durante o início da sessão.
                client.write(b'auto' if opts.check else b'show')
                client.waitForBytesWritten(1500)
            else:
                print(_('The other instance is starting. Open the application again in a few seconds.'), file=sys.stderr)
            return 0
        try:
            state = State(directory / 'state.json')
        except Exception as exc:
            if not opts.check:
                QMessageBox.warning(None, _('Could not open the history'), str(exc))
            return 1
        trial = None
        channel = None
        if opts.homologacao_github:
            from .github_trial import GitHubTrial
            trial = GitHubTrial(directory)
        else:
            from .github_channel import GitHubChannel
            try:
                channel = GitHubChannel(directory, state)
            except Exception as exc:
                if not opts.check:
                    QMessageBox.warning(None, _('Could not open the history'), str(exc))
                return 1
        window = Window(state, directory, automatic=opts.check, github_trial=trial, github_channel=channel,
                        preferences=preferences)
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        QLocalServer.removeServer(socket_path)
        if not server.listen(socket_path):
            print(_('Could not create the single-instance channel.'), file=sys.stderr)
            return 1
        clients = set()
        def connected():
            client = server.nextPendingConnection()
            clients.add(client)
            request = bytearray()
            def read():
                request.extend(bytes(client.readAll()))
                if len(request) < 4 and any(command.startswith(request) for command in (b'show', b'auto')):
                    return
                if request == b'show':
                    window.show()
                    window.raise_()
                    window.activateWindow()
                    window.reload()
                # b'auto': uma instância já está aberta (manual ou da sessão); a
                # verificação repetida não abre outra janela nem fica residente.
                client.disconnectFromServer()
            client.readyRead.connect(read)
            QTimer.singleShot(2000, client.disconnectFromServer)
            client.disconnected.connect(lambda: (clients.discard(client), client.deleteLater()))
            if client.bytesAvailable():
                read()
        server.newConnection.connect(connected)
    if opts.check:
        # Sem anúncio para apresentar, o processo do autostart termina em silêncio.
        # app.quit pelo laço de eventos, fora do slot da consulta.
        window.idle.connect(lambda: QTimer.singleShot(0, app.quit))
    else:
        window.show()
    QTimer.singleShot(60000 if opts.check else 0, window.reload)
    result = app.exec()
    if window.worker is not None:
        window.worker.wait()
    return result
