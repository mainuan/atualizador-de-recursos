"""Janela clássica: apresentação aprovada ligada aos fluxos existentes."""
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QListWidget, QMainWindow, QPlainTextEdit, QVBoxLayout,
)

from .catalog import CatalogError, Config
from .classic import ClassicContent, text_label as label
from .controller import Controller, Worker
from .localization import localize_standard_buttons
from .packages import build_plan, identity
from .repository import Repository
from .session import system_identity


class Window(QMainWindow):
    def __init__(self, state, directory=None, automatic=False, demo=None, github_trial=None, github_channel=None):
        super().__init__()
        self.state = state
        self.directory = directory
        self.automatic = automatic
        self.demo = demo
        self.github_trial = github_trial
        self.github_channel = github_channel
        self.catalog = None
        self.online = False
        self.system = {}
        self.plans = {}
        self.worker = None
        self.current = None
        self.active_release = None
        self.package_error = ''
        self.load_error = ''
        self._primary_focus_pending = True
        self.setWindowTitle('Atualizador de Recursos do Mainuan' + (' — Demonstração' if demo else ' — Homologação GitHub' if github_trial else ''))
        self.setWindowIcon(QIcon.fromTheme('mainuan-recursos', QIcon.fromTheme('system-software-update')))
        self.resize(720, 420)
        self.view = ClassicContent('Verificando novidades…')
        self.setCentralWidget(self.view)
        self.summary = self.view.message
        for name in ('know', 'install', 'later', 'status', 'progress', 'illustration', 'program_labels'):
            setattr(self, name, getattr(self.view, name))
        self.options = self.view.options
        self.refresh = self.view.menu.addAction('Verificar novidades')
        self.history_action = self.view.menu.addAction('Histórico de novidades')
        self.view.menu.addSeparator()
        self.details_action = self.view.menu.addAction('Informações técnicas')
        self.history = QListWidget()
        self.history.setAccessibleName('Histórico de novidades')
        self.history_dialog = self._auxiliary_dialog('Histórico de novidades', self.history)
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setAccessibleName('Programas, pacotes, versões e situação real')
        self.details_dialog = self._auxiliary_dialog('Informações técnicas', self.details_text)
        kwargs = dict(plan_provider=demo.plan, effects_validator=demo.effects,
                      transaction_factory=demo.transaction) if demo else {}
        if github_channel:
            from .github_channel import GitHubController
            self.controller = GitHubController(github_channel, self, guard=self._guard)
        elif github_trial:
            from .github_trial import GitHubController
            self.controller = GitHubController(github_trial, self, guard=self._guard)
        else:
            self.controller = Controller(self, guard=self._guard, **kwargs)
        self.controller.prepared.connect(self._confirm)
        self.controller.completed.connect(self._completed)
        self.controller.progress.connect(self._progress)
        self.controller.busyChanged.connect(self._enable)
        self.refresh.triggered.connect(self.reload)
        self.history_action.triggered.connect(self.show_history)
        self.details_action.triggered.connect(self.show_details)
        self.know.clicked.connect(self.open_article)
        self.install.clicked.connect(self.prepare)
        self.later.clicked.connect(self.postpone)
        self.history.currentRowChanged.connect(self.select)
        self.timer = QTimer(self)
        self.timer.setInterval(3600000)
        self.timer.timeout.connect(self.reload)
        if automatic:
            self.timer.start()
        self._enable()

    def _auxiliary_dialog(self, title, content):
        dialog = QDialog(self)
        dialog.setWindowTitle(title + (' — Demonstração' if self.demo else ''))
        layout = QVBoxLayout(dialog)
        layout.addWidget(content)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        localize_standard_buttons(buttons)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(min(520, self.width() - 24), min(360, self.height() - 24))
        return dialog

    def show_history(self):
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

    def show_details(self):
        self.details_text.setPlainText(self._technical_text())
        self.details_dialog.show()
        self.details_dialog.raise_()
        self.details_dialog.activateWindow()

    def _technical_text(self):
        if not self.current:
            return ''
        release = self.current
        plan = self.plans.get(release.key)
        rows = {r.name: r for r in plan.rows} if plan else {}
        lines = [release.title, f'Lançamento: {release.id} • {release.version}',
                 f'Matéria oficial: {release.article_url}', '']
        for feature in release.features:
            lines.append(feature.title)
            for requested in feature.packages:
                row = rows.get(requested.name)
                lines.extend((f'  Pacote: {requested.name}',
                    f'  Versão mínima: {requested.min_version}',
                    f'  Instalada: {row.installed or "não instalado" if row else "não verificada"}',
                    f'  Disponível: {row.candidate or "indisponível" if row else "não verificada"}',
                    f'  Arquitetura: {row.architecture if row else requested.architecture or "não verificada"}',
                    f'  Situação: {row.status if row else "pacotes não verificados"}'))
                if requested.sha256:
                    lines.append(f'  SHA-256 aprovado: {requested.sha256}')
            lines.append('')
        lines.append('A operação completa, incluindo dependências, será apresentada na confirmação da instalação.')
        if self.demo:
            lines.append('Demonstração: autorização e instalação simuladas; nenhum pacote será alterado.')
        elif self.github_channel:
            lines.extend(('', 'Canal oficial GitHub: packages.txt e message.txt no mesmo commit.',
                          'Pacotes de releases estáveis, com IDs, versões e SHA-256 registrados na consulta.',
                          'O download começa somente após escolher instalar; alterações não anunciadas são bloqueadas.',
                          'HTTPS e SHA-256 não equivalem à assinatura de um repositório APT.',
                          'O PackageKit/PolicyKit pode solicitar autorização para origem não confiável.'))
        elif self.github_trial:
            lines.extend(('', 'Homologação GitHub: origem oficial e artefato fixados por IDs e SHA-256.',
                          'O download começa somente após escolher instalar.',
                          'Arquivo local sem assinatura de repositório APT. O PackageKit/PolicyKit pode solicitar autorização para origem não confiável.',
                          'O ensaio permite somente o aplicativo Gestão de Drivers; alterações em outros pacotes são bloqueadas.'))
        return '\n'.join(lines)

    def _enable(self, _=False):
        busy = bool(self.worker or self.controller.busy or self.controller.awaiting)
        plan = self.plans.get(self.current.key) if self.current else None
        compatible = self.current and self.current.compatible(self.system)
        self.refresh.setEnabled(not busy)
        self.history.setEnabled(not busy)
        self.history_action.setEnabled(not busy)
        self.details_action.setEnabled(not busy and self.current is not None)
        self.know.setEnabled(not busy and self.current is not None)
        self.install.setEnabled(bool(not busy and compatible and self.online and plan and plan.pending and not plan.blockers))
        self.later.setEnabled(not busy and self.current is not None)
        self.progress.setVisible(bool(self.worker or self.controller.busy))
        if self._primary_focus_pending and self.install.isEnabled():
            self.install.setFocus(Qt.FocusReason.OtherFocusReason)
            self._primary_focus_pending = False

    def reload(self):
        if self.worker or self.controller.busy or self.controller.awaiting:
            return
        self.status.setText('Consultando as novidades oficiais do Mainuan…')
        self.progress.setRange(0, 0)
        def load():
            if self.demo:
                catalog, online = self.demo.catalog, True
                system = {'distro_id': 'mainuan', 'version_id': '26.04', 'architecture': 'amd64'}
                plans = {r.key: self.demo.plan(r) for r in catalog.releases if r.compatible(system)}
            else:
                if self.github_channel:
                    catalog, online = self.github_channel.load()
                elif self.github_trial:
                    catalog, online = self.github_trial.load()
                else:
                    config = Config.load()
                    catalog, online = Repository(config, self.directory, state=self.state).load()
                system = {}
                try:
                    system = system_identity()
                    if self.github_channel:
                        plans = {r.key: self.github_channel.plan(r) for r in catalog.releases if r.compatible(system)}
                    elif self.github_trial:
                        plans = {r.key: self.github_trial.plan(r) for r in catalog.releases if r.compatible(system)}
                    else:
                        import apt
                        cache = apt.Cache()
                        plans = {r.key: build_plan(r, cache) for r in catalog.releases if r.compatible(system)}
                except Exception as exc:
                    return catalog, online, system, {}, str(exc) or type(exc).__name__
            return catalog, online, system, plans, ''
        self.worker = Worker(load, self)
        worker = self.worker
        def done():
            self.worker = None
            try:
                if worker.error:
                    raise CatalogError(worker.error)
                catalog, online, system, plans, package_error = worker.value
                self.state.accept(catalog)
                self.catalog, self.online, self.system, self.plans = catalog, online, system, plans
                self.package_error = package_error
                self.load_error = ''
                self.populate()
            except Exception as exc:
                self.online = False
                self.load_error = f'Não foi possível verificar as novidades. {exc}'
                self.status.setText(self.load_error)
            worker.deleteLater()
            self._enable()
        worker.finished.connect(done)
        self._enable()
        worker.start()

    def populate(self):
        due = [r for r in self.catalog.releases if r.compatible(self.system) and self.state.due(r)]
        previous = self.current.key if self.current else None
        self.history.blockSignals(True)
        self.history.clear()
        for release in self.catalog.releases:
            plan = self.plans.get(release.key)
            if plan:
                self.state.observe(release, plan)
            self.history.addItem(self._history_text(release))
        selected = next((i for i, r in enumerate(self.catalog.releases) if r.key == previous), 0)
        if self.automatic and not self.isVisible() and due:
            selected = self.catalog.releases.index(due[0])
        self.history.setCurrentRow(selected if self.catalog.releases else -1)
        self.history.blockSignals(False)
        self.select(selected if self.catalog.releases else -1)
        if self.automatic and due and not self.isVisible():
            self.show()
            self.mark_viewed()
        if not self.catalog.releases:
            self.status.setText('Ainda não há novidades publicadas. Volte em breve!')

    def select(self, index):
        self.current = self.catalog.releases[index] if self.catalog and 0 <= index < len(self.catalog.releases) else None
        self.view.set_programs(())
        if not self.current:
            self.summary.setText('Nenhuma novidade publicada.\nVolte em breve para conhecer os próximos recursos do Mainuan.')
            self.details_text.clear()
            self._enable()
            return
        self.summary.setText(self.current.summary)
        self.view.set_programs(feature.title or ', '.join(p.name for p in feature.packages)
                               for feature in self.current.features)
        plan = self.plans.get(self.current.key)
        if self.package_error:
            message = f'Não foi possível verificar os pacotes: {self.package_error}'
        elif not self.current.compatible(self.system):
            message = 'Este lançamento não é compatível com a versão ou arquitetura deste sistema.'
        elif plan and plan.complete:
            message = 'Você já recebeu estes recursos pelo sistema. Conheça as novidades!'
        elif plan and plan.blockers:
            message = 'Alguns pacotes ainda não estão disponíveis para instalação segura. Consulte as informações técnicas no menu.'
        else:
            message = 'Temos novidades para você! Conheça os recursos antes de instalar.'
        if not self.online:
            message += ' Catálogo em cache: consulta offline; instalação indisponível.'
        if self.load_error:
            message = self.load_error
        self.status.setText(message)
        self.status.setHidden(message == 'Temos novidades para você! Conheça os recursos antes de instalar.')
        self.details_text.setPlainText(self._technical_text())
        if self.isVisible():
            self.mark_viewed()
        self._enable()

    def _history_text(self, release):
        plan = self.plans.get(release.key)
        editorial = {'unseen': 'Nova', 'viewed': 'Visualizada', 'postponed': 'Adiada'}[
            self.state.entry(release)['presentation']]
        received = ' • Já recebido' if plan and plan.complete else ''
        return f'{release.title}\n{release.version} • {editorial}{received}'

    def mark_viewed(self):
        if self.current:
            try:
                self.state.viewed(self.current)
                item = self.history.currentItem()
                if item:
                    item.setText(self._history_text(self.current))
            except OSError as exc:
                self.status.setText(f'Não foi possível salvar a visualização no histórico: {exc}')

    def showEvent(self, event):
        super().showEvent(event)
        if self.install.isEnabled():
            self.install.setFocus(Qt.FocusReason.OtherFocusReason)
        self.mark_viewed()

    def open_article(self):
        if self.current:
            self.mark_viewed()
            if not QDesktopServices.openUrl(QUrl(self.current.article_url)):
                self.status.setText('Não foi possível abrir o navegador padrão.')

    def _guard(self):
        if not self.online or not self.catalog or datetime.now(timezone.utc) >= self.catalog.expires_at:
            raise CatalogError('Verifique novamente o catálogo oficial antes de instalar.')
        if not self.active_release or not self.active_release.compatible(self.system):
            raise CatalogError('Lançamento incompatível com este sistema.')

    def prepare(self):
        if self.current:
            self.active_release = self.current
            self.controller.prepare(self.current)

    @staticmethod
    def _exact_announced_operation(prepared):
        """Somente os efeitos já validados e anunciados dispensam outro clique."""
        rows = prepared.plan.pending
        if prepared.plan.blockers or not rows or {r.name for r in prepared.plan.rows} != {p.name for p in prepared.release.packages}:
            return False
        expected = {(r.name, r.candidate, r.architecture, r.installed) for r in rows}
        try:
            actual = {(*identity(package_id), installed) for info, package_id, installed in prepared.evidence if info in (11, 12)}
        except ValueError:
            return False
        return (len(expected) == len(rows) == len(prepared.evidence)
                and all(info in (11, 12) for info, _, _ in prepared.evidence)
                and actual == expected)

    def _confirm(self, prepared):
        if self._exact_announced_operation(prepared):
            # O clique inicial já expressou a intenção. confirm() ainda revalida
            # plano, origens, hashes, simulação e efeitos antes de executar.
            self.controller.confirm(prepared)
            return
        self._enable()
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit
        dialog = QDialog(self)
        dialog.setWindowTitle('Confirmar instalação' + (' — Demonstração' if self.demo else ''))
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('A instalação precisa alterar outros pacotes ou revisar o plano. Confira a operação antes de continuar.'))
        details = QPlainTextEdit()
        details.setReadOnly(True)
        direct = '\n'.join(f'{r.name}: {r.installed or "não instalado"} → {r.candidate}' for r in prepared.plan.pending)
        effects = '\n'.join(f'{package_id.split(";")[0]} → {package_id.split(";")[1]} ({package_id.split(";")[2]})'
                            for _, package_id, _ in prepared.evidence)
        details.setPlainText(direct + '\n\nOperação completa, incluindo dependências:\n' + effects)
        details.setAccessibleName('Pacotes e dependências da operação')
        layout.addWidget(details)
        layout.addWidget(label('Autorização e instalação serão simuladas.' if self.demo else
                               'O sistema solicitará autorização para instalar.'))
        buttons = QDialogButtonBox()
        buttons.addButton('Instalar novidades', QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = buttons.addButton('Cancelar', QDialogButtonBox.ButtonRole.RejectRole)
        cancel.setDefault(True)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        screen = self.screen().availableGeometry()
        dialog.resize(min(600, screen.width() - 32), min(420, screen.height() - 48))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.confirm(prepared)
        else:
            self.controller.cancel_preparation()
            self.status.setText('Instalação cancelada. Você pode conhecer as novidades quando quiser.')
            self._enable()

    def _completed(self, success, message, plan):
        if plan and self.active_release:
            self.plans[self.active_release.key] = plan
            try:
                self.state.observe(self.active_release, plan)
            except OSError as exc:
                message += f'\nNão foi possível salvar o histórico: {exc}'
            self.select(self.history.currentRow())
        self.status.setText(message)
        self._enable()

    def _progress(self, message, percentage):
        self.status.setText(message)
        self.progress.setRange(0, 100 if percentage is not None else 0)
        if percentage is not None:
            self.progress.setValue(percentage)

    def postpone(self):
        if self.current:
            try:
                self.state.postpone(self.current)
            except OSError as exc:
                self.status.setText(f'Não foi possível salvar o adiamento de 24 horas: {exc}')
                return
        self.close()

    def closeEvent(self, event):
        if self.worker or self.controller.busy or self.controller.awaiting:
            event.ignore()
            self.status.setText('Aguarde o término da operação antes de fechar.')
        else:
            self.history_dialog.reject()
            self.details_dialog.reject()
            if self.automatic:
                self.hide()
                event.ignore()
            else:
                super().closeEvent(event)
