from dataclasses import replace
import unittest

from mainuan_recursos.controller import Controller
from mainuan_recursos.demo import Demo
from mainuan_recursos.packages import PlanningError
from qt_support import APP, wait_until


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.demo = Demo()
        self.controller = Controller(plan_provider=self.demo.plan, effects_validator=self.demo.effects,
                                     transaction_factory=self.demo.transaction)
        self.prepared, self.completed = [], []
        self.controller.prepared.connect(self.prepared.append)
        self.controller.completed.connect(lambda *args:self.completed.append(args))

    def tearDown(self):
        if self.controller.worker:
            self.controller.worker.wait(2000)
        self.controller.deleteLater()

    def prepare(self):
        self.controller.prepare(self.demo.release)
        wait_until(lambda:self.prepared or self.completed)

    def confirm(self):
        self.controller.confirm(self.prepared[0])
        wait_until(lambda:bool(self.completed))

    def test_no_install_before_confirmation_then_real_verification(self):
        self.prepare()
        self.assertFalse(self.demo.installed)
        self.assertFalse(self.completed)
        self.assertEqual(len(self.prepared[0].evidence),3)
        self.confirm()
        self.assertTrue(self.completed[0][0])
        self.assertTrue(self.completed[0][2].complete)

    def test_cancel_confirmation_never_mutates(self):
        self.prepare()
        self.controller.cancel_preparation()
        self.controller.confirm(self.prepared[0])
        self.assertFalse(self.controller.busy)
        self.assertFalse(self.demo.installed)

    def test_forged_prepared_object_is_ignored(self):
        self.prepare()
        self.controller.confirm(replace(self.prepared[0]))
        self.assertFalse(self.controller.busy)
        self.assertFalse(self.demo.installed)
        self.controller.cancel_preparation()

    def test_installed_resources_skip_transaction(self):
        self.demo.installed = True
        self.controller.transaction_factory = lambda _:self.fail('Não deveria criar transação')
        self.prepare()
        self.assertTrue(self.completed[0][0])
        self.assertFalse(self.prepared)

    def test_unavailable_resources_block_installation(self):
        self.demo.scenario = 'indisponivel'
        self.prepare()
        self.assertFalse(self.completed[0][0])
        self.assertFalse(self.demo.installed)

    def test_plan_changed_after_confirmation_requires_new_confirmation(self):
        self.prepare()
        self.demo.scenario = 'parcial'
        self.confirm()
        self.assertFalse(self.completed[0][0])
        self.assertIn('mudaram',self.completed[0][1])
        self.assertFalse(self.demo.installed)

    def test_dependency_change_blocks_mutation(self):
        self.prepare()
        self.controller.effects_validator = lambda effects, expected: ('changed',)
        self.confirm()
        self.assertFalse(self.completed[0][0])
        self.assertIn('dependências',self.completed[0][1])
        self.assertFalse(self.demo.installed)

    def test_failed_and_cancelled_mutations_have_no_success_claim(self):
        for scenario in ('erro','cancelado'):
            self.demo.scenario = scenario
            self.prepared.clear()
            self.completed.clear()
            self.prepare()
            self.confirm()
            self.assertFalse(self.completed[0][0])
            self.assertFalse(self.demo.installed)

    def test_finished_success_without_installed_evidence_is_not_success(self):
        self.prepare()
        initial_plan = self.prepared[0].plan
        self.controller.plan_provider = lambda _: initial_plan
        self.confirm()
        self.assertFalse(self.completed[0][0])
        self.assertIn('não foram confirmadas',self.completed[0][1])

    def test_expired_catalog_blocks_execution(self):
        self.prepare()
        def guard():
            raise ValueError('Catálogo expirado')
        self.controller.guard = guard
        self.confirm()
        self.assertFalse(self.completed[0][0])
        self.assertFalse(self.demo.installed)

    def test_untrusted_dependencies_block_preparation(self):
        def validate(*_):
            raise PlanningError('Origem não confiável')
        self.controller.effects_validator = validate
        self.prepare()
        self.assertFalse(self.completed[0][0])
        self.assertFalse(self.prepared)
