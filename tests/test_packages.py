import unittest

from mainuan_recursos.packages import PlanningError, build_plan, identity, validate_effects, version_compare
from helpers import package, release


class PlanningTests(unittest.TestCase):
    def cache(self, **kwargs):
        return {p.name: package(**kwargs) for p in release().packages}

    def test_new_programs_do_not_require_prefix_or_installation(self):
        result = build_plan(release(), self.cache())
        self.assertEqual(len(result.pending), 2)
        self.assertFalse(result.blockers)

    def test_adequate_and_newer_versions_not_reinstalled(self):
        for current in ('2.0.0', '3.0.0'):
            result = build_plan(release(), self.cache(installed=current, candidate='4.0.0'))
            self.assertTrue(result.complete)
            self.assertFalse(result.pending)

    def test_versions_use_debian_semantics(self):
        self.assertLess(version_compare('1.0~rc1', '1.0'), 0)
        self.assertGreater(version_compare('1:1.0', '9.0'), 0)
        self.assertGreater(version_compare('1.10', '1.9'), 0)

    def test_older_installed_can_be_updated(self):
        result = build_plan(release(), self.cache(installed='1.0'))
        self.assertTrue(all(r.status == 'Atualizar' for r in result.pending))

    def test_external_updates_visible_without_installing(self):
        cache = self.cache(installed='2.0.0', candidate=None)
        self.assertTrue(build_plan(release(), cache).complete)

    def test_missing_untrusted_held_old_and_broken_block(self):
        for kwargs in ({'candidate':None}, {'trust':False}, {'hold':True},
                       {'candidate':'1.0'}, {'installed':'1.0','configured':False}):
            with self.subTest(kwargs=kwargs):
                self.assertTrue(build_plan(release(), self.cache(**kwargs)).blockers)
        self.assertEqual(len(build_plan(release(), {}).blockers), 2)

    def test_mixed_received_and_pending(self):
        cache = self.cache()
        cache['mainuan-boas-vindas'] = package(installed='2.0.0')
        result = build_plan(release(), cache)
        self.assertEqual([p.name for p in result.pending], ['mainuan-personalizacao'])

    def test_effects_include_trusted_dependencies(self):
        cache = {'mainuan-boas-vindas': package(), 'dependency': package()}
        effects = ((12,'mainuan-boas-vindas;2.0.0;amd64;repo'), (12,'dependency;2.0.0;amd64;repo'))
        evidence = validate_effects(effects, (('mainuan-boas-vindas','2.0.0','amd64'),), cache)
        self.assertEqual(len(evidence),2)

    def test_removal_downgrade_reinstall_untrusted_unknown_effects_rejected(self):
        for info in (13, 15, 19, 20, 23, 0, 99):
            with self.subTest(info=info), self.assertRaises(PlanningError):
                validate_effects(((info,'foo;2.0.0;amd64;repo'),), (), {'foo':package()})

    def test_all_dependencies_must_be_trusted_not_held_or_already_installed(self):
        for kwargs in ({'trust':False}, {'installed':'2.0.0'}, {'installed':'3.0.0'}, {'hold':True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(PlanningError):
                validate_effects(((12,'foo;2.0.0;amd64;repo'),), (), {'foo':package(**kwargs)})

    def test_unknown_missing_version_wrong_architecture_and_omitted_request_rejected(self):
        for cache in ({}, {'foo':package(candidate='1.0')}, {'foo':package(arch='i386')}):
            with self.assertRaises(PlanningError):
                validate_effects(((12,'foo;2.0.0;amd64;repo'),), (), cache)
        with self.assertRaises(PlanningError):
            validate_effects((), (('foo','2.0.0','amd64'),), {})

    def test_invalid_package_identity(self):
        for value in ('foo', 'foo;2;;repo', 'foo;2;amd64;repo;other'):
            with self.assertRaises(PlanningError):
                identity(value)

    def test_catalog_can_offer_package_without_mainuan_prefix(self):
        from dataclasses import replace
        from mainuan_recursos.catalog import Feature, Package
        announcement = replace(release(), features=(Feature('Programa novo', (Package('programa-novo','1.0'),)),))
        plan = build_plan(announcement, {'programa-novo':package(candidate='1.1')})
        self.assertEqual(plan.pending[0].name,'programa-novo')
