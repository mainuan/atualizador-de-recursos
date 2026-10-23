import unittest
from PyQt6.QtCore import QObject, pyqtSignal

from mainuan_recursos.packagekit import ROOT, TX, SIMULATE, ONLY_TRUSTED, Transaction
from qt_support import APP


class FakeTransport(QObject):
    eventReceived = pyqtSignal(str, object)
    lost = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.calls = []
        self.unsubscribed = False
        self.reply_error = None
        self.fail_subscribe = False
        self.path = '/org/freedesktop/PackageKit/transactions/test'

    def call(self, path, interface, method, args, callback):
        self.calls.append((method, args))
        callback([self.path] if method == 'CreateTransaction' else [], self.reply_error)

    def subscribe(self, path):
        return not self.fail_subscribe

    def unsubscribe(self):
        self.unsubscribed = True


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tx = Transaction(transport_factory=FakeTransport)
        self.results = []
        self.tx.finished.connect(self.results.append)

    def tearDown(self):
        self.tx.timeout.stop()
        self.tx.deleteLater()

    def event(self, name, *args):
        self.tx.transport.eventReceived.emit(name, list(args))

    def test_resolve_is_not_mutating_and_ack_is_not_success(self):
        self.tx.start('Resolve', ['foo'])
        self.assertFalse(self.results)
        self.assertFalse(self.tx.transport.interactive)
        self.assertEqual(self.tx.transport.calls[-1], ('Resolve', [2,['foo']]))
        self.event('Finished', 1, 10)
        self.assertTrue(self.results[0].success)
        self.assertTrue(self.tx.transport.unsubscribed)

    def test_only_trusted_simulate_flags_and_interactive_authorization(self):
        self.tx.start('InstallPackages', ['foo;1;all;repo'], simulate=True)
        self.assertEqual(self.tx.transport.calls[-1][1][0], ONLY_TRUSTED | SIMULATE)
        self.assertFalse(self.tx.transport.interactive)

    def test_real_install_requires_confirmed_authorization(self):
        with self.assertRaises(ValueError):
            self.tx.start('InstallPackages', ['foo;1;all;repo'])
        self.assertFalse(self.tx.transport.calls)

    def test_confirmed_mutation_is_interactive(self):
        self.tx.start('InstallPackages', ['foo;1;all;repo'], authorized=True)
        self.assertTrue(self.tx.transport.interactive)
        self.assertEqual(self.tx.transport.calls[-1][1][0], ONLY_TRUSTED)
        self.assertFalse(self.tx.timeout.isActive())

    def test_error_followed_by_success_exit_is_failure(self):
        self.tx.start('Resolve',['foo'])
        self.event('ErrorCode', 46, 'A autorização foi negada')
        self.event('Finished', 1, 1)
        self.assertFalse(self.results[0].success)
        self.assertIn('46', self.results[0].error)

    def test_cancel_failed_destroy_and_lost(self):
        for name, args in (('Finished',(3,1)), ('Destroy',()), ('lost',())):
            tx = Transaction(transport_factory=FakeTransport)
            results = []
            tx.finished.connect(results.append)
            tx.start('Resolve',['foo'])
            if name == 'lost':
                tx.transport.lost.emit()
            else:
                tx.transport.eventReceived.emit(name,list(args))
            self.assertFalse(results[0].success)
            tx.deleteLater()

    def test_mutation_timeout_waits_for_finished(self):
        self.tx.start('InstallPackages',['foo;1;all;repo'],authorized=True)
        self.tx._reply([],('org.freedesktop.DBus.Error.NoReply','timeout'))
        self.assertFalse(self.results)
        self.event('Finished',1,1)
        self.assertTrue(self.results[0].success)

    def test_mutation_daemon_loss_marks_uncertain(self):
        self.tx.start('InstallPackages',['foo;1;all;repo'],authorized=True)
        self.tx.transport.lost.emit()
        self.assertIn('parcial',self.results[0].error)

    def test_progress_unknown_percentage_and_restart(self):
        progress = []
        self.tx.progress.connect(lambda message,value:progress.append(value))
        self.tx.start('Resolve',['foo'])
        for percent in (101, 20):
            self.event('PropertiesChanged',TX,{'Percentage':percent},[])
        self.assertEqual(progress,[None,20])
        self.event('RequireRestart',4,'foo;1;all;repo')
        self.event('Finished',1,1)
        self.assertEqual(self.results[0].restart,4)

    def test_bad_path_subscription_and_method_error(self):
        for variant in ('path','subscription','reply'):
            tx = Transaction(transport_factory=FakeTransport)
            results = []
            tx.finished.connect(results.append)
            if variant == 'path':
                tx.transport.path = ROOT
            elif variant == 'subscription':
                tx.transport.fail_subscribe = True
            else:
                tx.transport.reply_error = ('NotAuthorized','Sem autorização')
            tx.start('Resolve',['foo'])
            self.assertFalse(results[0].success)
            tx.deleteLater()

    def test_terminal_signals_emit_once_and_single_use(self):
        self.tx.start('Resolve',['foo'])
        self.event('Finished',1,1)
        self.event('Destroy')
        self.assertEqual(len(self.results),1)
        with self.assertRaises(RuntimeError):
            self.tx.start('Resolve',['foo'])
