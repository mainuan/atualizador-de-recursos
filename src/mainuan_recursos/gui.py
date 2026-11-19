"""Janela clássica: apresentação aprovada ligada aos fluxos existentes."""
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QListWidget, QMainWindow, QPlainTextEdit, QVBoxLayout,
)

from .catalog import CatalogError, Config
from .classic import ClassicContent, text_label as label
from .controller import Controller, Worker
from .i18n import _, pgettext
from .localization import localize_standard_buttons
from .packages import RECEIVED, build_plan, identity, status_text
from .repository import Repository
from .session import system_identity


class Window(QMainWindow):
    # Verificação automática terminada sem nada a apresentar: o processo pode encerrar.
    idle = pyqtSignal()

    def __init__(self, state, directory=None, automatic=False, demo=None, github_trial=None, github_channel=None,
                 preferences=None):
        super().__init__()
        self.state = state
        self.preferences = preferences
        self.active = None
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
        self.setWindowTitle(_('Mainuan Feature Updater — Demo') if demo else
                            _('Mainuan Feature Updater — GitHub Acceptance Test') if github_trial else
                            _('Mainuan Feature Updater'))
        self.setWindowIcon(QIcon.fromTheme('mainuan-recursos', QIcon.fromTheme('system-software-update')))
        self.resize(720, 420)
        self.view = ClassicContent(_('Checking for news…'))
        self.setCentralWidget(self.view)
        self.summary = self.view.message
        for name in ('know', 'install', 'later', 'status', 'progress', 'illustration', 'program_labels'):
            setattr(self, name, getattr(self.view, name))
        self.options = self.view.options
        self.refresh = self.view.menu.addAction(_('Check for News'))
        self.history_action = self.view.menu.addAction(_('News History'))
        self.automatic_action = None
        if preferences is not None:
            self.automatic_action = self.view.menu.addAction(_('Show News at Login'))
            self.automatic_action.setCheckable(True)
            self.automatic_action.setChecked(preferences.automatic)
            self.automatic_action.toggled.connect(self._set_automatic)
        self.view.menu.addSeparator()
        self.details_action = self.view.menu.addAction(_('Technical Information'))
        self.history = QListWidget()
        self.history.setAccessibleName(_('News History'))
        self.history_dialog = self._auxiliary_dialog(_('News History'), self.history)
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setAccessibleName(_('Programs, packages, versions and actual status'))
        self.details_dialog = self._auxiliary_dialog(_('Technical Information'), self.details_text)
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
        self._enable()

    def _set_automatic(self, enabled):
        try:
            self.preferences.set_automatic(enabled)
        except OSError as exc:
            self.automatic_action.blockSignals(True)
            self.automatic_action.setChecked(self.preferences.automatic)
            self.automatic_action.blockSignals(False)
            self.status.setText(_('Could not save the preference: {error}').format(error=exc))

    def _auxiliary_dialog(self, title, content):
        dialog = QDialog(self)
        # Translators: title of an auxiliary window opened in demonstration mode.
        dialog.setWindowTitle(_('{title} — Demo').format(title=title) if self.demo else title)
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
        lines = [release.title, _('Release: {id} • {version}').format(id=release.id, version=release.version),
                 _('Official article: {url}').format(url=release.article_url), '']
        not_checked = _('not checked')
        for feature in release.features:
            lines.append(feature.title)
            for requested in feature.packages:
                row = rows.get(requested.name)
                installed = (row.installed or _('not installed')) if row else not_checked
                available = (row.candidate or _('unavailable')) if row else not_checked
                architecture = row.architecture if row else requested.architecture or not_checked
                status = status_text(row.status) if row else _('packages not checked')
                lines.extend(('  ' + _('Package: {name}').format(name=requested.name),
                    '  ' + _('Minimum version: {version}').format(version=requested.min_version),
                    '  ' + _('Installed: {version}').format(version=installed),
                    '  ' + _('Available: {version}').format(version=available),
                    '  ' + _('Architecture: {architecture}').format(architecture=architecture),
                    '  ' + _('Status: {status}').format(status=status)))
                if requested.sha256:
                    lines.append('  ' + _('Approved SHA-256: {sha256}').format(sha256=requested.sha256))
            lines.append('')
        lines.append(_('The complete operation, including dependencies, will be shown when confirming the installation.'))
        if self.demo:
            lines.append(_('Demo: authorization and installation are simulated; no package will be changed.'))
        elif self.github_channel:
            lines.extend(('', _('Official GitHub channel: announcements.json, read from a single commit and published explicitly.'),
                          _('Packages from stable releases, with IDs, versions and SHA-256 recorded during the query.'),
                          _('The download starts only after choosing to install; unannounced changes are blocked.'),
                          _('HTTPS and SHA-256 are not equivalent to an APT repository signature.'),
                          _('PackageKit/PolicyKit may ask for authorization for an untrusted source.')))
        elif self.github_trial:
            lines.extend(('', _('GitHub acceptance test: official source and artifact pinned by IDs and SHA-256.'),
                          _('The download starts only after choosing to install.'),
                          _('Local file without an APT repository signature. PackageKit/PolicyKit may ask for authorization for an untrusted source.'),
                          _('The trial only allows the Driver Manager application; changes to other packages are blocked.')))
        return '\n'.join(lines)

    def _enable(self, _=False):
        busy = bool(self.worker or self.controller.busy or self.controller.awaiting)
        plan = self.plans.get(self.current.key) if self.current else None
        compatible = self.current and self.current.compatible(self.system)
        self.refresh.setEnabled(not busy)
        self.history.setEnabled(not busy)
        self.history_action.setEnabled(not busy)
        self.details_action.setEnabled(not busy and self.current is not None)
        self.know.setEnabled(not busy and self.current is not None and bool(self.current.article_url))
        # Anúncio só informativo: sem link e sem programas, sem botões inúteis.
        self.know.setVisible(self.current is None or bool(self.current.article_url))
        self.install.setVisible(self.current is None or bool(self.current.packages))
        self.install.setEnabled(bool(not busy and compatible and self.online and plan and plan.pending and not plan.blockers))
        self.later.setEnabled(not busy and self.current is not None)
        self.progress.setVisible(bool(self.worker or self.controller.busy))
        if self._primary_focus_pending and self.install.isEnabled():
            self.install.setFocus(Qt.FocusReason.OtherFocusReason)
            self._primary_focus_pending = False

    def reload(self):
        if self.worker or self.controller.busy or self.controller.awaiting:
            return
        self.status.setText(_('Querying the official Mainuan news…'))
        self.progress.setRange(0, 0)
        def load():
            if self.demo:
                catalog, online = self.demo.catalog, True
                system = {'distro_id': 'mainuan', 'version_id': '26.04', 'architecture': 'amd64'}
                plans = {r.key: self.demo.plan(r) for r in catalog.releases if r.compatible(system)}
            else:
                active = None
                if self.github_channel:
                    catalog, online = self.github_channel.load()
                    active = self.github_channel.active
                elif self.github_trial:
                    catalog, online = self.github_trial.load()
                else:
                    config = Config.load()
                    catalog, online = Repository(config, self.directory, state=self.state).load()
                system = {}
                try:
                    system = system_identity()
                    if self.github_channel:
                        # A verificação automática só olha o anúncio ativo; o histórico
                        # é consultado quando o usuário abre o aplicativo.
                        targets = [r for r in catalog.releases if r.compatible(system)
                                   and (not automatic or r.key == active)]
                        plans = {r.key: self.github_channel.plan(r) for r in targets}
                    elif self.github_trial:
                        plans = {r.key: self.github_trial.plan(r) for r in catalog.releases if r.compatible(system)}
                    else:
                        import apt
                        cache = apt.Cache()
                        plans = {r.key: build_plan(r, cache) for r in catalog.releases if r.compatible(system)}
                except Exception as exc:
                    return catalog, online, system, {}, str(exc) or type(exc).__name__, active
                return catalog, online, system, plans, '', active
            return catalog, online, system, plans, '', None
        automatic = self.automatic and not self.isVisible()
        self.worker = Worker(load, self)
        worker = self.worker
        def done():
            self.worker = None
            try:
                if worker.error:
                    raise CatalogError(worker.error)
                catalog, online, system, plans, package_error, active = worker.value
                self.state.accept(catalog)
                self.catalog, self.online, self.system, self.plans = catalog, online, system, plans
                self.active = active
                self.package_error = package_error
                self.load_error = ''
                self.populate()
            except Exception as exc:
                self.online = False
                self.load_error = _('Could not check for news. {error}').format(error=exc)
                self.status.setText(self.load_error)
            worker.deleteLater()
            self._enable()
            if self.automatic and not self.isVisible():
                # Nada a apresentar (ou consulta sem sucesso): silêncio total.
                self.idle.emit()
        worker.finished.connect(done)
        self._enable()
        worker.start()

    def presentable(self):
        """Novidades que podem abrir a janela sozinhas (modo automático).

        No canal GitHub: só o anúncio ativo da consulta online que acabou de
        terminar, compatível, ainda não apresentado (ou adiado e vencido) e com
        a preferência do usuário ligada.  Cache, histórico e consultas com
        falha nunca abrem a janela.
        """
        if self.preferences is not None and not self.preferences.automatic:
            return []
        due = [r for r in self.catalog.releases if r.compatible(self.system) and self.state.due(r)]
        if self.github_channel:
            return [r for r in due if self.online and self.active and r.key == self.active]
        return due

    def populate(self):
        due = self.presentable()
        previous = self.current.key if self.current else None
        self.history.blockSignals(True)
        self.history.clear()
        for release in self.catalog.releases:
            plan = self.plans.get(release.key)
            if plan:
                self.state.observe(release, plan)
            self.history.addItem(self._history_text(release))
        default = 0
        if self.github_channel:
            # Sem anúncio ativo, a janela diz claramente que nada foi publicado;
            # as edições anteriores continuam no histórico.
            default = next((i for i, r in enumerate(self.catalog.releases) if r.key == self.active), -1)
        selected = next((i for i, r in enumerate(self.catalog.releases) if r.key == previous), default)
        if self.automatic and not self.isVisible() and due:
            selected = self.catalog.releases.index(due[0])
        self.history.setCurrentRow(selected if self.catalog.releases else -1)
        self.history.blockSignals(False)
        self.select(selected if self.catalog.releases else -1)
        if self.automatic and due and not self.isVisible():
            self.show()
            self.mark_viewed()
        if not self.catalog.releases:
            self.status.setText(_('No news has been published yet. Come back soon!'))
        elif self.current is None and not self.load_error:
            self.status.setText(_('No news is published right now. Earlier news is in the history.'))

    def select(self, index):
        self.current = self.catalog.releases[index] if self.catalog and 0 <= index < len(self.catalog.releases) else None
        self.view.set_programs(())
        if not self.current:
            self.summary.setText(_('No news published.\nCome back soon to discover the next Mainuan features.'))
            self.details_text.clear()
            self._enable()
            return
        self.summary.setText(self.current.summary)
        self.view.set_programs(feature.title or ', '.join(p.name for p in feature.packages)
                               for feature in self.current.features)
        plan = self.plans.get(self.current.key)
        welcome = _('We have news for you! Discover the features before installing.')
        if self.package_error:
            message = _('Could not check the packages: {error}').format(error=self.package_error)
        elif not self.current.compatible(self.system):
            message = _('This release is not compatible with the version or architecture of this system.')
        elif plan and plan.complete:
            message = _('You have already received these features through the system. Discover the news!')
        elif plan and plan.blockers:
            message = _('Some packages are not yet available for safe installation. See the technical information in the menu.')
        else:
            message = welcome
        if not self.online:
            message = _('{message} Cached catalog: offline query; installation unavailable.').format(message=message)
        if self.load_error:
            message = self.load_error
        self.status.setText(message)
        self.status.setHidden(message == welcome)
        self.details_text.setPlainText(self._technical_text())
        if self.isVisible():
            self.mark_viewed()
        self._enable()

    def _history_text(self, release):
        plan = self.plans.get(release.key)
        editorial = {'unseen': pgettext('news state', 'New'), 'viewed': pgettext('news state', 'Viewed'),
                     'postponed': pgettext('news state', 'Postponed')}[self.state.entry(release)['presentation']]
        received = ' • ' + status_text(RECEIVED) if plan and plan.complete else ''
        return f'{release.title}\n{release.version} • {editorial}{received}'

    def mark_viewed(self):
        if self.current:
            try:
                self.state.viewed(self.current)
                item = self.history.currentItem()
                if item:
                    item.setText(self._history_text(self.current))
            except OSError as exc:
                self.status.setText(_('Could not save the viewing in the history: {error}').format(error=exc))

    def showEvent(self, event):
        super().showEvent(event)
        if self.install.isEnabled():
            self.install.setFocus(Qt.FocusReason.OtherFocusReason)
        self.mark_viewed()

    def open_article(self):
        if self.current:
            self.mark_viewed()
            if not QDesktopServices.openUrl(QUrl(self.current.article_url)):
                self.status.setText(_('Could not open the default web browser.'))

    def _guard(self):
        if not self.online or not self.catalog or datetime.now(timezone.utc) >= self.catalog.expires_at:
            raise CatalogError(_('Check the official catalog again before installing.'))
        if not self.active_release or not self.active_release.compatible(self.system):
            raise CatalogError(_('Release incompatible with this system.'))

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
        dialog.setWindowTitle(_('Confirm Installation — Demo') if self.demo else _('Confirm Installation'))
        layout = QVBoxLayout(dialog)
        layout.addWidget(label(_('The installation needs to change other packages or review the plan. Check the operation before continuing.')))
        details = QPlainTextEdit()
        details.setReadOnly(True)
        not_installed = _('not installed')
        direct = '\n'.join(f'{r.name}: {r.installed or not_installed} → {r.candidate}' for r in prepared.plan.pending)
        effects = '\n'.join(f'{package_id.split(";")[0]} → {package_id.split(";")[1]} ({package_id.split(";")[2]})'
                            for _, package_id, _ in prepared.evidence)
        details.setPlainText(direct + '\n\n' + _('Complete operation, including dependencies:') + '\n' + effects)
        details.setAccessibleName(_('Packages and dependencies of the operation'))
        layout.addWidget(details)
        layout.addWidget(label(_('Authorization and installation will be simulated.') if self.demo else
                               _('The system will ask for authorization to install.')))
        buttons = QDialogButtonBox()
        buttons.addButton(_('Install New Features'), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = buttons.addButton(_('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
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
            self.status.setText(_('Installation canceled. You can discover the news whenever you want.'))
            self._enable()

    def _completed(self, success, message, plan):
        if plan and self.active_release:
            self.plans[self.active_release.key] = plan
            try:
                self.state.observe(self.active_release, plan)
            except OSError as exc:
                message += '\n' + _('Could not save the history: {error}').format(error=exc)
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
                self.status.setText(_('Could not save the 24-hour postponement: {error}').format(error=exc))
                return
        self.close()

    def closeEvent(self, event):
        if self.worker or self.controller.busy or self.controller.awaiting:
            event.ignore()
            self.status.setText(_('Wait for the operation to finish before closing.'))
        else:
            self.history_dialog.reject()
            self.details_dialog.reject()
            # Também no modo automático: fechar encerra o processo da sessão,
            # que não fica residente nem verifica de hora em hora.
            super().closeEvent(event)
