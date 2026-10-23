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
from .localization import install_pt_br
from .session import SessionKind, session_kind
from .state import State, state_directory


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conheça e receba as novidades oficiais do Mainuan.')
    parser.add_argument('--check', action='store_true', help='verificar durante a sessão e notificar sem bloquear o login')
    parser.add_argument('--homologacao-github', action='store_true', help='ensaio real e manual em VM: packages.txt/message.txt do GitHub e Gestão de Drivers 1.0')
    parser.add_argument('--demo', action='store_true', help='demonstrar o fluxo inteiro sem modificar o sistema')
    parser.add_argument('--scenario', choices=SCENARIOS, default='novo', help='cenário de demonstração')
    parser.add_argument('--test-catalog', type=Path, help='catálogo local assinado, somente com --demo')
    parser.add_argument('--test-config', type=Path, help='configuração e chave de teste, somente com --demo')
    parser.add_argument('--version', action='version', version=__version__)
    opts = parser.parse_args(argv)
    if opts.homologacao_github:
        if opts.check or opts.demo or opts.test_catalog or opts.test_config:
            parser.error('--homologacao-github é manual e não pode ser combinado com --check/--demo.')
        from .github_trial import check_vm
        try:
            check_vm()
        except Exception as exc:
            parser.exit(1, f'Homologação indisponível: {exc}\n')
    if (opts.test_catalog or opts.test_config) and not (opts.demo and opts.test_catalog and opts.test_config):
        parser.error('Use --demo --test-catalog ARQUIVO --test-config ARQUIVO juntos.')
    session = SessionKind.INSTALLED if opts.demo else session_kind()
    if session != SessionKind.INSTALLED and opts.check:
        return 0
    app = QApplication(sys.argv[:1])
    install_pt_br(app)
    app.setApplicationName('mainuan-atualizador-recursos')
    app.setOrganizationName('Mainuan')
    app.setDesktopFileName('org.mainuan.Recursos')
    app.setQuitOnLastWindowClosed(not opts.check)
    if session != SessionKind.INSTALLED:
        message = ('A verificação de novidades fica disponível após instalar o Mainuan. A sessão Live não será consultada.'
                   if session == SessionKind.LIVE else
                   'Não foi possível determinar o tipo de sessão. A consulta e a instalação de recursos foram desabilitadas.')
        QMessageBox.information(None, 'Novidades do Mainuan', message)
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
                QMessageBox.warning(None, 'Catálogo de teste inválido', str(exc))
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
                print(f'Não foi possível abrir o diretório de estado: {exc}', file=sys.stderr)
            else:
                QMessageBox.warning(None, 'Não foi possível abrir o histórico', str(exc))
            return 1
        lock = QLockFile(str(directory / 'session.lock'))
        lock.setStaleLockTime(0)
        socket_path = str(directory / 'session.socket')
        if not lock.tryLock(0):
            if lock.error() != QLockFile.LockError.LockFailedError:
                print('Não foi possível bloquear o estado local. Verifique as permissões do diretório.', file=sys.stderr)
                return 1
            client = QLocalSocket()
            client.connectToServer(socket_path)
            if client.waitForConnected(1500):
                # O autostart preserva verificações mesmo se a primeira instância
                # foi aberta manualmente durante o início da sessão.
                client.write(b'auto' if opts.check else b'show')
                client.waitForBytesWritten(1500)
            else:
                print('A outra instância está iniciando. Abra o aplicativo novamente em alguns segundos.', file=sys.stderr)
            return 0
        try:
            state = State(directory / 'state.json')
        except Exception as exc:
            if not opts.check:
                QMessageBox.warning(None, 'Não foi possível abrir o histórico', str(exc))
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
                    QMessageBox.warning(None, 'Não foi possível abrir o histórico', str(exc))
                return 1
        window = Window(state, directory, automatic=opts.check, github_trial=trial, github_channel=channel)
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        QLocalServer.removeServer(socket_path)
        if not server.listen(socket_path):
            print('Não foi possível criar o canal da instância única.', file=sys.stderr)
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
                elif request == b'auto' and not window.automatic:
                    window.automatic = True
                    app.setQuitOnLastWindowClosed(False)
                    window.timer.start()
                    QTimer.singleShot(60000, window.reload)
                client.disconnectFromServer()
            client.readyRead.connect(read)
            QTimer.singleShot(2000, client.disconnectFromServer)
            client.disconnected.connect(lambda: (clients.discard(client), client.deleteLater()))
            if client.bytesAvailable():
                read()
        server.newConnection.connect(connected)
    if not opts.check:
        window.show()
    QTimer.singleShot(60000 if opts.check else 0, window.reload)
    return app.exec()
