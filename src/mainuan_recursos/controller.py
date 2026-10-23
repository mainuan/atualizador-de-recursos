"""Coordenação de operações, independente dos Widgets."""
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .packages import PlanningError, build_plan, identity, validate_effects
from .packagekit import Transaction


class Worker(QThread):
    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.value = None
        self.error = None

    def run(self):
        try:
            self.value = self.function()
        except Exception as exc:
            self.error = str(exc) or type(exc).__name__


@dataclass(frozen=True)
class Prepared:
    release: object
    plan: object
    ids: tuple
    evidence: tuple


class Controller(QObject):
    prepared = pyqtSignal(object)
    completed = pyqtSignal(bool, str, object)
    progress = pyqtSignal(str, object)
    busyChanged = pyqtSignal(bool)

    def __init__(self, parent=None, plan_provider=build_plan, effects_validator=validate_effects,
                 transaction_factory=Transaction, guard=lambda: None):
        super().__init__(parent)
        self.plan_provider = plan_provider
        self.effects_validator = effects_validator
        self.transaction_factory = transaction_factory
        self.guard = guard
        self.busy = False
        self.awaiting = None
        self.worker = None
        self.transaction = None
        self.release = None
        self.confirmed = None

    def _set_busy(self, busy):
        self.busy = busy
        self.busyChanged.emit(busy)

    def _work(self, function, callback):
        self.worker = Worker(function, self)
        worker = self.worker

        def done():
            self.worker = None
            if worker.error:
                self._fail(worker.error)
            else:
                callback(worker.value)
            worker.deleteLater()
        worker.finished.connect(done)
        worker.start()

    def prepare(self, release):
        if self.busy or self.awaiting:
            return
        self.release = release
        self.confirmed = None
        self._set_busy(True)
        self.progress.emit('Verificando os pacotes anunciados…', None)
        try:
            self.guard()
        except Exception as exc:
            return self._fail(str(exc))
        self._work(lambda: self.plan_provider(release), self._planned)

    def _planned(self, plan):
        if plan.blockers:
            return self._fail('Não é possível preparar a instalação:\n' + '\n'.join(f'{r.name}: {r.status}' for r in plan.blockers), plan)
        if plan.complete:
            return self._finish(True, 'Você já recebeu todos os recursos deste lançamento.', plan)
        if self.confirmed and plan != self.confirmed.plan:
            return self._fail('Os pacotes mudaram. Prepare a instalação novamente para revisar a operação.', plan)
        self.plan = plan
        self._tx('Resolve', tuple(r.name for r in plan.pending), False, self._resolved)

    def _tx(self, method, values, simulate, callback):
        if self.transaction:
            self.transaction.deleteLater()
        self.transaction = self.transaction_factory(self)
        self.transaction.progress.connect(self.progress)
        self.transaction.finished.connect(callback)
        self.transaction.start(method, values, simulate=simulate, authorized=bool(self.confirmed))

    def _resolved(self, result):
        if not result.success:
            return self._fail(result.error)
        try:
            expected = {r.identity for r in self.plan.pending}
            found = {identity(package_id): package_id for info, package_id in result.packages if info == 2}
            if not expected <= found.keys():
                raise PlanningError('O PackageKit não encontrou as versões/arquiteturas planejadas nos repositórios.')
            self.ids = tuple(sorted(found[key] for key in expected))
            if self.confirmed and self.ids != self.confirmed.ids:
                raise PlanningError('A origem ou a versão dos pacotes mudou. Revise uma nova operação.')
        except PlanningError as exc:
            return self._fail(str(exc))
        self.progress.emit('Simulando a instalação e verificando dependências…', None)
        self._tx('InstallPackages', self.ids, True, self._simulated)

    def _simulated(self, result):
        if not result.success:
            return self._fail(result.error)
        pins = {r.identity: r.sha256 for r in self.plan.pending if r.sha256}
        kwargs = {'pins': pins} if self.effects_validator is validate_effects else {}
        self._work(lambda: self.effects_validator(result.packages,
                   tuple(r.identity for r in self.plan.pending), **kwargs), self._validated)

    def _validated(self, evidence):
        if self.confirmed:
            if evidence != self.confirmed.evidence:
                return self._fail('As dependências mudaram. Prepare uma nova operação para confirmar os detalhes.')
            try:
                self.guard()
            except Exception as exc:
                return self._fail(str(exc))
            self.progress.emit('Instalando novidades; a autorização será solicitada pelo sistema…', None)
            self._tx('InstallPackages', self.ids, False, self._installed)
        else:
            self.awaiting = Prepared(self.release, self.plan, self.ids, evidence)
            self._set_busy(False)
            self.prepared.emit(self.awaiting)

    def confirm(self, prepared):
        if self.busy or prepared is not self.awaiting or self.awaiting is None:
            return
        self.awaiting = None
        self.confirmed = prepared
        self._set_busy(True)
        self.progress.emit('Revalidando a operação confirmada…', None)
        self._work(lambda: self.plan_provider(self.release), self._planned)

    def cancel_preparation(self):
        if not self.busy:
            self.awaiting = None

    def _installed(self, result):
        self.progress.emit('Conferindo as versões realmente instaladas…', None)
        def verified(plan):
            success = result.success and plan.complete
            message = ('As novidades foram instaladas e verificadas. Aproveite!' if success else
                       result.error or 'O PackageKit encerrou a operação, mas as versões instaladas ainda não foram confirmadas.')
            if result.restart >= 2:
                message += '\nO sistema solicitou reinício de aplicativo, sessão ou computador.'
            self._finish(success, message, plan)
        # Mesmo após falhas, observar o estado real para não ocultar resultados parciais.
        self._work(lambda: self.plan_provider(self.release), verified)

    def _fail(self, message, plan=None):
        self._finish(False, message, plan)

    def _finish(self, success, message, plan):
        self.awaiting = None
        self.confirmed = None
        self._set_busy(False)
        self.completed.emit(success, message, plan)
