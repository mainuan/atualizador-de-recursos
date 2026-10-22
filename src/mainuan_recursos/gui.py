"""Interface nativa Qt6 do Atualizador de Recursos do Mainuan."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import sys

from PyQt6.QtCore import QProcess, QProcessEnvironment, QSettings, QThread, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from . import __version__
from .backend import ResourceUpdate, is_live_session, scan_resources


class ScanWorker(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: list[ResourceUpdate] = []
        self.error = ''

    def run(self) -> None:
        try:
            self.result = scan_resources()
        except Exception as exc:
            self.error = str(exc)


class MainWindow(QMainWindow):
    def __init__(self, silent: bool):
        super().__init__()
        self.silent = silent
        self.updates: list[ResourceUpdate] = []
        self.worker: ScanWorker | None = None
        self.process: QProcess | None = None
        self.action = ''
        self.settings = QSettings('Mainuan', 'AtualizadorDeRecursos')

        self.setWindowTitle('Atualizador de Recursos — Mainuan')
        self.setWindowIcon(QIcon.fromTheme('system-software-update'))
        self.setMinimumSize(580, 370)
        self.resize(760, 470)

        root = QWidget(self)
        self.setCentralWidget(root)
        column = QVBoxLayout(root)
        column.setSpacing(12)

        heading = QLabel('Atualizador de Recursos do Mainuan')
        font = heading.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        heading.setFont(font)
        column.addWidget(heading)

        self.status = QLabel('Verificando os recursos instalados...')
        self.status.setWordWrap(True)
        column.addWidget(self.status)

        self.table = QTreeWidget()
        self.table.setHeaderLabels(['Recurso', 'Versão instalada', 'Nova versão'])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setUniformRowHeights(True)
        self.table.setAccessibleName('Recursos com atualizações disponíveis')
        column.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        column.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(400)
        self.log.setPlaceholderText('O resultado da operação aparecerá aqui.')
        self.log.setMaximumHeight(110)
        self.log.setVisible(False)
        column.addWidget(self.log)

        buttons = QHBoxLayout()
        self.check_button = QPushButton('Verificar')
        self.refresh_button = QPushButton('Atualizar listas')
        self.install_button = QPushButton('Instalar recursos')
        self.later_button = QPushButton('Depois' if silent else 'Fechar')
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.later_button)
        column.addLayout(buttons)

        self.check_button.clicked.connect(self.start_scan)
        self.refresh_button.clicked.connect(self.refresh_indexes)
        self.install_button.clicked.connect(self.install_resources)
        self.later_button.clicked.connect(self.postpone_or_close)
        self._set_busy(True)
        QTimer.singleShot(0, self.start_scan)

    def _set_busy(self, busy: bool) -> None:
        self.check_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.install_button.setEnabled(not busy and bool(self.updates))
        self.progress.setVisible(busy)

    def start_scan(self) -> None:
        if self.worker is not None or self.process is not None:
            return
        self.status.setText('Consultando os pacotes de recursos do Mainuan...')
        self._set_busy(True)
        self.worker = ScanWorker(self)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _worker_finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is None:
            return
        worker.deleteLater()
        if worker.error:
            self.scan_failed(worker.error)
        else:
            self.scan_finished(worker.result)

    def scan_finished(self, updates: list[ResourceUpdate]) -> None:
        self.updates = updates
        self.table.clear()
        for update in updates:
            item = QTreeWidgetItem([update.package, update.installed, update.candidate])
            item.setToolTip(0, update.description)
            self.table.addTopLevelItem(item)
        for i in range(3):
            self.table.resizeColumnToContents(i)
        self._set_busy(False)
        if updates:
            self.status.setText(
                f'{len(updates)} recurso(s) do Mainuan com atualização disponível. '
                'A instalação solicitará autorização de administrador.'
            )
            if self.silent:
                self.show()
        else:
            self.status.setText('Todos os recursos acompanhados estão atualizados.')
            if self.silent:
                QApplication.instance().quit()

    def scan_failed(self, reason: str) -> None:
        self._set_busy(False)
        if self.silent:
            print(f'Falha na consulta de recursos: {reason}', file=sys.stderr)
            QApplication.instance().quit()
        else:
            self.status.setText('Não foi possível consultar os recursos.')
            QMessageBox.warning(self, 'Erro na verificação', reason)

    def _run_apt(self, action: str, args: list[str]) -> None:
        if self.worker is not None or self.process is not None:
            return
        self.action = action
        self.log.clear()
        self.log.setVisible(True)
        self._set_busy(True)
        self.status.setText('Aguardando autorização administrativa...')
        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('LC_ALL', 'C')
        env.insert('DEBIAN_FRONTEND', 'noninteractive')
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.start('/usr/bin/pkexec', ['/usr/bin/apt-get', *args])

    def _read_output(self) -> None:
        if self.process is not None:
            chunk = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
            if chunk:
                self.log.appendPlainText(chunk.rstrip())

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return
        if self.process is not None:
            self.process.deleteLater()
            self.process = None
        self._set_busy(False)
        self.status.setText('Não foi possível iniciar a operação administrativa.')
        QMessageBox.warning(self, 'Não foi possível executar',
                            'O pkexec não pôde ser iniciado. Verifique se está instalado.')

    def _process_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._read_output()
        action = self.action
        if self.process is not None:
            self.process.deleteLater()
            self.process = None
        self._set_busy(False)
        if status == QProcess.ExitStatus.NormalExit and code == 0:
            if action == 'install':
                self.status.setText('Instalação concluída. Verificando novamente...')
                QMessageBox.information(self, 'Concluído',
                                        'Os recursos selecionados foram atualizados com sucesso.')
            else:
                self.status.setText('Listas de pacotes atualizadas.')
            self.start_scan()
        else:
            self.status.setText('A operação foi cancelada ou apresentou um erro.')
            QMessageBox.warning(self, 'Atualização não concluída',
                                'A atualização não foi concluída. Consulte os detalhes exibidos.')

    def refresh_indexes(self) -> None:
        answer = QMessageBox.question(
            self, 'Atualizar listas de pacotes',
            'Atualizar as listas do APT? Esta operação solicitará sua senha de administrador.',
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run_apt('refresh', ['update'])

    def install_resources(self) -> None:
        if not self.updates:
            return
        names = [update.package for update in self.updates]
        answer = QMessageBox.question(
            self, 'Confirmar atualização',
            f'Instalar atualizações para {len(names)} recurso(s) do Mainuan?\n\n'
            + '\n'.join(names)
            + '\n\nAs dependências necessárias também podem ser instaladas.',
        )
        if answer == QMessageBox.StandardButton.Yes:
            # Sem shell: apenas nomes obtidos dos metadados do próprio APT.
            self._run_apt('install', ['install', '--yes', '--only-upgrade', '--no-remove', '--', *names])

    def postpone_or_close(self) -> None:
        if self.silent and self.updates:
            until = datetime.now().astimezone() + timedelta(days=1)
            self.settings.setValue('postponed_until', until.isoformat())
        self.close()

    def closeEvent(self, event) -> None:
        if self.process is not None or self.worker is not None:
            event.ignore()
            QMessageBox.information(self, 'Operação em andamento',
                                    'Aguarde o término da operação antes de fechar esta janela.')
            return
        super().closeEvent(event)


def is_postponed(settings: QSettings) -> bool:
    value = settings.value('postponed_until', '')
    if not value:
        return False
    try:
        return datetime.fromisoformat(str(value)) > datetime.now().astimezone()
    except (TypeError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description='Atualizador de Recursos do Mainuan')
    parser.add_argument('--check', action='store_true', help='notifica apenas se houver atualizações')
    parser.add_argument('--version', action='version', version=__version__)
    opts = parser.parse_args()
    if opts.check and is_live_session():
        return 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName('AtualizadorDeRecursos')
    app.setOrganizationName('Mainuan')
    if opts.check and is_postponed(QSettings('Mainuan', 'AtualizadorDeRecursos')):
        return 0
    window = MainWindow(silent=opts.check)
    if not opts.check:
        window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
