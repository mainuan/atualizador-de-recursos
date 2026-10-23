"""Transações PackageKit assíncronas por QtDBus; sem dependência de Widgets."""
from dataclasses import dataclass
import re

from PyQt6 import QtDBus
from PyQt6.QtCore import QObject, QMetaType, QTimer, pyqtSignal, pyqtSlot

SERVICE = 'org.freedesktop.PackageKit'
ROOT = '/org/freedesktop/PackageKit'
TX = SERVICE + '.Transaction'
PROPERTIES = 'org.freedesktop.DBus.Properties'
ONLY_TRUSTED = 1 << 1
SIMULATE = 1 << 2


@dataclass(frozen=True)
class Result:
    success: bool
    packages: tuple = ()
    error: str = ''
    restart: int = 0


class Transport(QObject):
    eventReceived = pyqtSignal(str, object)
    lost = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = QtDBus.QDBusConnection.systemBus()
        self.subscriptions = []
        self.watchers = set()

    def call(self, path, interface, method, args, callback):
        message = QtDBus.QDBusMessage.createMethodCall(SERVICE, path, interface, method)
        args = list(args)
        if method in ('Resolve', 'InstallPackages', 'InstallFiles'):
            args[0] = QtDBus.QDBusArgument(args[0], QMetaType.Type.ULongLong.value)
            args[1] = QtDBus.QDBusArgument(args[1], QMetaType.Type.QStringList.value)
        elif method == 'SetHints':
            args[0] = QtDBus.QDBusArgument(args[0], QMetaType.Type.QStringList.value)
        message.setArguments(args)
        # args[0] is now a QDBusArgument; authorization derives from the stored flag.
        interactive = method in ('InstallPackages', 'InstallFiles') and self.interactive
        message.setInteractiveAuthorizationAllowed(interactive)
        watcher = QtDBus.QDBusPendingCallWatcher(self.bus.asyncCall(message, 300000 if interactive else 30000), self)
        self.watchers.add(watcher)

        def done(pending):
            reply = QtDBus.QDBusPendingReply(pending).reply()
            error = (reply.errorName(), reply.errorMessage()) if reply.type() == QtDBus.QDBusMessage.MessageType.ErrorMessage else None
            self.watchers.discard(pending)
            pending.deleteLater()
            callback(reply.arguments(), error)
        watcher.finished.connect(done)

    def subscribe(self, path):
        connections = [(SERVICE, path, TX, name, self._event) for name in
                       ('Package', 'Finished', 'ErrorCode', 'RequireRestart', 'Destroy')]
        connections += [(SERVICE, path, PROPERTIES, 'PropertiesChanged', self._event),
                        ('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                         'NameOwnerChanged', self._owner)]
        for connection in connections:
            if not self.bus.connect(*connection):
                self.unsubscribe()
                return False
            self.subscriptions.append(connection)
        return True

    def unsubscribe(self):
        for connection in self.subscriptions:
            self.bus.disconnect(*connection)
        self.subscriptions.clear()

    @pyqtSlot(QtDBus.QDBusMessage)
    def _event(self, message):
        self.eventReceived.emit(message.member(), message.arguments())

    @pyqtSlot(str, str, str)
    def _owner(self, name, old, new):
        if name == SERVICE and old and old != new:
            self.lost.emit()


class Transaction(QObject):
    finished = pyqtSignal(object)
    progress = pyqtSignal(str, object)

    def __init__(self, parent=None, transport_factory=Transport, allow_local_files=False):
        super().__init__(parent)
        self.transport = transport_factory(self)
        self.allow_local_files = allow_local_files
        self.transport.eventReceived.connect(self._event)
        self.transport.lost.connect(self._lost)
        self.done = False
        self.started = False
        self.packages = set()
        self.error = ''
        self.restart = 0
        self.path = None
        self.real = False
        self.properties = {}
        self.submitted = False
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self._timed_out)

    def start(self, method, values, simulate=False, authorized=False):
        if self.started:
            raise RuntimeError('Transação já utilizada.')
        self.started = True
        if method not in ('Resolve', 'InstallPackages') and not (self.allow_local_files and method == 'InstallFiles'):
            raise ValueError('Operação não permitida.')
        if method in ('InstallPackages', 'InstallFiles') and not simulate and not authorized:
            raise ValueError('A instalação exige um plano confirmado.')
        self.real = method in ('InstallPackages', 'InstallFiles') and not simulate
        self.transport.interactive = self.real
        self.method = method
        # InstallFiles é a API nativa para arquivos locais: autorização específica
        # pelo PolicyKit. ONLY_TRUSTED exige assinatura APT, inexistente em .deb
        # avulso; permanece obrigatório em todas as operações InstallPackages.
        flags = (SIMULATE if simulate else 0) if method == 'InstallFiles' else ONLY_TRUSTED | (SIMULATE if simulate else 0)
        self.arguments = [2 if method == 'Resolve' else flags, list(values)]
        self.timeout.start(120000)
        self.transport.call(ROOT, SERVICE, 'CreateTransaction', [], self._created)

    def _created(self, args, error):
        if self.done:
            return
        if error:
            return self._fail(error)
        path = args[0] if args else ''
        self.path = path.path() if isinstance(path, QtDBus.QDBusObjectPath) else path
        if not isinstance(self.path, str) or self.path == ROOT or not re.fullmatch(r'/[A-Za-z0-9_/]+', self.path):
            return self._fail(('invalid-path', 'Caminho de transação inválido.'))
        if not self.transport.subscribe(self.path):
            return self._fail(('signals', 'Não foi possível acompanhar a transação.'))
        self.transport.call(self.path, TX, 'SetHints', [[
            'interactive=' + ('true' if self.real else 'false'), 'locale=pt_BR.UTF-8', 'cache-age=2147483647']], self._hinted)

    def _hinted(self, args, error):
        if self.done:
            return
        if error:
            return self._fail(error)
        self.submitted = True
        if self.real:
            self.timeout.stop()  # Não abandonar mutação por tempo arbitrário.
        self.transport.call(self.path, TX, self.method, self.arguments, self._reply)

    def _reply(self, args, error):
        if self.done or not error:
            return
        if self.real and error[0] in ('org.freedesktop.DBus.Error.NoReply', 'org.freedesktop.DBus.Error.Timeout'):
            self.progress.emit('Aguardando o resultado do PackageKit; a operação pode continuar em andamento.', None)
            return
        self._fail(error)

    @pyqtSlot(str, object)
    def _event(self, name, args):
        if self.done:
            return
        if name == 'Package':
            self.packages.add((int(args[0]), str(args[1])))
        elif name == 'ErrorCode':
            self.error = f'PackageKit ({args[0]}): {args[1]}'
        elif name == 'RequireRestart':
            self.restart = max(self.restart, int(args[0]))
        elif name == 'PropertiesChanged' and args[0] == TX:
            props = args[1]
            if not isinstance(props, dict):
                self.progress.emit('Processando a transação…', None)
                return
            self.properties.update(props)
            for key in args[2] if len(args) > 2 else ():
                self.properties.pop(key, None)
            percentage = self.properties.get('Percentage')
            status = {8: 'Baixando novidades...', 9: 'Instalando novidades...', 10: 'Instalando novidades...',
                      30: 'Aguardando outro gerenciador de pacotes...',
                      31: 'Aguardando autorização...'}.get(self.properties.get('Status'), 'Preparando instalação...')
            self.progress.emit(status, percentage if isinstance(percentage, int) and 0 <= percentage <= 100 else None)
            if len(args) > 2 and args[2]:
                self.transport.call(self.path, PROPERTIES, 'GetAll', [TX], self._properties)
        elif name == 'Finished':
            self._finish(Result(args[0] == 1 and not self.error, tuple(sorted(self.packages)),
                                self.error or ('' if args[0] == 1 else f'Operação cancelada ou não concluída (código {args[0]}).'), self.restart))
        elif name == 'Destroy':
            self._fail(('destroyed', 'Transação encerrada sem confirmação de conclusão.'))

    def _properties(self, args, error):
        if not self.done and not error and args:
            self._event('PropertiesChanged', [TX, args[0], []])

    def _lost(self):
        self._fail(('disconnected', 'O serviço PackageKit foi desconectado.'))

    def _timed_out(self):
        self._fail(('timeout', 'A consulta do PackageKit excedeu o tempo limite.'))

    def _fail(self, error):
        suffix = ' O resultado pode ser parcial; verifique novamente os pacotes.' if self.real and self.submitted else ''
        self._finish(Result(False, tuple(sorted(self.packages)), f'{error[0]}: {error[1]}{suffix}', self.restart))

    def _finish(self, result):
        if self.done:
            return
        self.done = True
        self.timeout.stop()
        self.transport.unsubscribe()
        self.finished.emit(result)
