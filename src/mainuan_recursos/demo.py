"""Cenários em memória; nenhum transporte ou consulta do sistema é criado."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .catalog import Catalog, Feature, Package, Release
from .i18n import _
from .packages import INSTALL, RECEIVED, PackageRow, Plan
from .packagekit import Result

SCENARIOS = ('novo', 'visualizado', 'adiado', 'instalado', 'parcial', 'indisponivel', 'incompativel', 'erro', 'cancelado')


class Demo:
    def __init__(self, scenario='novo'):
        self.scenario = scenario
        self.installed = scenario == 'instalado'
        self.received = {}
        self.release = Release('mainuan-boas-vindas', '1.0', _('Your Mainuan is evolving!'),
                               _('Discover the new features prepared to make your day simpler.'),
                               'https://mainuan.example/novidades/boas-vindas', (
                                   Feature(_('A new welcome experience'), (Package('mainuan-boas-vindas', '1.2'),)),
                                   Feature(_('More options to customize your desktop'), (Package('mainuan-personalizacao', '2.0'),)),
                                   Feature(_('A hub to discover Mainuan applications'), (Package('mainuan-aplicativos', '1.0'),)),
                               ), {'distro_id': ['outra-distribuicao']} if scenario == 'incompativel' else {})
        old = replace(self.release, id='mainuan-anterior', version='1.0', title=_('Previous Mainuan news'))
        self.catalog = Catalog(1, datetime.now(timezone.utc) + timedelta(days=7), (self.release, old), 'demo')

    def plan(self, release):
        self.requested_release = release
        rows = []
        for index, package in enumerate(release.packages):
            received = ((package.name, package.min_version) in self.received
                        or (self.installed and not self.received)
                        or (self.scenario == 'parcial' and index == 0))
            status = (RECEIVED if received else _('Unavailable in the repositories')
                      if self.scenario == 'indisponivel' else INSTALL)
            rows.append(PackageRow(package.name, package.min_version,
                                   package.min_version if received else '', package.min_version,
                                   package.architecture or 'amd64', status, package.sha256))
        return Plan(tuple(rows))

    def effects(self, effects, expected):
        return tuple(sorted((info, package_id, '') for info, package_id in effects))

    def transaction(self, parent):
        return DemoTransaction(self, parent)


class DemoTransaction(QObject):
    finished = pyqtSignal(object)
    progress = pyqtSignal(str, object)

    def __init__(self, demo, parent):
        super().__init__(parent)
        self.demo = demo

    def start(self, method, values, simulate=False, authorized=False):
        if method == 'Resolve':
            packages = tuple((2, f'{p.name};{p.min_version};{p.architecture or "amd64"};demo')
                             for p in self.demo.requested_release.packages if p.name in values)
            QTimer.singleShot(50, lambda: self.finished.emit(Result(True, packages)))
        elif simulate:
            QTimer.singleShot(50, lambda: self.finished.emit(Result(True, tuple((12, p) for p in values))))
        else:
            assert authorized
            self.progress.emit(_('Preparing installation...'), 0)
            QTimer.singleShot(250, lambda: self.progress.emit(_('Installing new features...'), 55))
            def finish():
                failed = self.demo.scenario in ('erro', 'cancelado')
                if not failed:
                    self.demo.installed = True
                    for package in self.demo.requested_release.packages:
                        self.demo.received[(package.name, package.min_version)] = True
                self.finished.emit(Result(not failed, error=_('Authorization canceled (simulation).') if self.demo.scenario == 'cancelado' else
                                          _('Download failed (simulation).') if failed else ''))
            QTimer.singleShot(600, finish)
