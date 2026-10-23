"""Regressões encontradas na auditoria e jornada de três programas."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt

from helpers import catalog, package, release
from mainuan_recursos.catalog import CatalogError, authenticate, scoped_url
from mainuan_recursos.controller import Controller, Worker
from mainuan_recursos.demo import Demo
from mainuan_recursos.gui import Window
from mainuan_recursos.packagekit import Transaction, TX
from mainuan_recursos.packages import PlanningError, validate_effects
from mainuan_recursos.repository import Repository
from mainuan_recursos.state import State
from qt_support import APP, wait_until
from test_packagekit import FakeTransport


class PersistenceAuditTests(unittest.TestCase):
    def test_failed_save_does_not_mark_release_viewed_or_postponed_in_memory(self):
        state, r = State(), release()
        for change in (lambda:state.viewed(r), lambda:state.postpone(r), lambda:state.accept(catalog())):
            previous = json.dumps(state.data,sort_keys=True)
            with patch.object(state, 'save', side_effect=OSError('Sem espaço')):
                with self.assertRaises(OSError):
                    change()
            self.assertEqual(json.dumps(state.data,sort_keys=True),previous)

    def test_unchanged_view_does_not_rewrite_disk(self):
        state, r = State(), release()
        state.viewed(r)
        with patch.object(state,'save') as save:
            state.viewed(r)
            save.assert_not_called()

    def test_validation_remains_enabled_with_python_optimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'state.json'
            path.write_text('{"sequence":-1,"digest":"","releases":{}}')
            code = ('from pathlib import Path; from mainuan_recursos.state import State; '
                    f'State(Path({str(path)!r}))')
            result = subprocess.run([sys.executable,'-O','-c',code],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('CatalogError',result.stderr)

    def test_signature_failure_precedes_catalog_processing(self):
        from mainuan_recursos.catalog import Config
        with patch('mainuan_recursos.catalog.parse_catalog') as parse:
            with self.assertRaises(CatalogError):
                authenticate(b'{invalid-json',b'{"key_id":"unknown","signature":"AA=="}',Config('',(),{}))
            parse.assert_not_called()

    def test_watermark_is_persisted_before_cache_and_apt(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            state=State(directory/'state.json')
            repository=Repository(None,directory,state=state)
            with patch('mainuan_recursos.repository.fetch',return_value=(b'json',b'signature')), \
                 patch('mainuan_recursos.repository.authenticate',return_value=c), \
                 patch('mainuan_recursos.repository.atomic_write',side_effect=OSError('Falha no cache')):
                with self.assertRaises(OSError):
                    repository.load()
            self.assertEqual(State(directory/'state.json').data['sequence'],c.sequence)
            # Mesmo após falha posterior, uma edição anterior é rejeitada.
            with self.assertRaises(CatalogError):
                state.accept(replace(c,sequence=0))

    def test_offline_cache_also_obeys_watermark(self):
        c=catalog()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            repo=Repository(None,directory,watermark=(2,'newer'))
            repo.cache.write_text('{"catalog":"eA==","signature":"eA=="}')
            with patch('mainuan_recursos.repository.fetch',side_effect=OSError('Offline')), \
                 patch('mainuan_recursos.repository.authenticate',return_value=c):
                with self.assertRaises(CatalogError):
                    repo.load()

    def test_unofficial_https_redirect_is_rejected_by_path(self):
        from mainuan_recursos.catalog import OfficialRedirects
        redirect=OfficialRedirects(('github.com',),('https://github.com/mainuan/',))
        with self.assertRaises(CatalogError):
            redirect.redirect_request(None,None,302,'',{},'https://github.com/outra-conta/repo')


class TransactionAuditTests(unittest.TestCase):
    def test_lock_and_authorization_are_distinct_and_progress_is_retained(self):
        tx=Transaction(transport_factory=FakeTransport)
        self.addCleanup(tx.deleteLater)
        tx.start('Resolve',['foo'])
        progress=[]
        tx.progress.connect(lambda text,number:progress.append((text,number)))
        tx._event('PropertiesChanged',[TX,{'Status':30,'Percentage':20},[]])
        tx._event('PropertiesChanged',[TX,{'Percentage':21},[]])
        self.assertIn('outro gerenciador',progress[-1][0])
        self.assertEqual(progress[-1][1],21)
        tx._event('PropertiesChanged',[TX,{'Status':31},[]])
        self.assertIn('autorização',progress[-1][0])
        self.assertEqual(progress[-1][1],21)
        tx._event('Finished',[1,0])

    def test_incompletely_configured_dependency_blocks_installation(self):
        with self.assertRaises(PlanningError):
            validate_effects(((12,'dep;2.0.0;amd64;repo'),),(),{'dep':package(installed='1.0',configured=False)})

    def test_multiarch_dependency_is_checked_against_correct_installation(self):
        cache={'dep':package(installed='1.0'), 'dep:i386':package(installed='3.0.0',arch='i386')}
        with self.assertRaises(PlanningError):
            validate_effects(((12,'dep;2.0.0;i386;repo'),),(),cache)

    def test_exception_without_message_is_still_reported(self):
        def broken():
            raise RuntimeError()
        worker=Worker(broken)
        worker.run()
        self.assertEqual(worker.error,'RuntimeError')


class ExperienceAuditTests(unittest.TestCase):
    def create(self,state=None,automatic=False):
        demo=Demo()
        window=Window(state or State(),demo=demo,automatic=automatic)
        self.addCleanup(window.deleteLater)
        window.reload()
        wait_until(lambda:window.worker is None)
        return window,demo,window.state

    def test_three_program_journey_postpone_manual_cancel_fail_success_and_next_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            window,demo,state=self.create(State(Path(tmp)/'state.json'),automatic=True)
            # O digest de demonstração não representa uma publicação real.
            demo.catalog=replace(demo.catalog,digest='d'*64)
            state.data['digest']='d'*64
            state.save()
            self.assertEqual(len(demo.release.packages),3)
            self.assertTrue(window.isVisible())
            self.assertEqual(state.entry(demo.release)['presentation'],'viewed')
            self.assertEqual(state.entry(demo.release)['packages'],'pending')
            with patch('mainuan_recursos.gui.QDesktopServices.openUrl',return_value=True) as browser:
                window.open_article()
                browser.assert_called_once()
            with patch('mainuan_recursos.state.time.time',return_value=1000):
                window.postpone()
            loaded=State(state.path)
            self.assertFalse(loaded.due(demo.release,now=87399))
            self.assertTrue(loaded.due(demo.release,now=87400))
            with patch('mainuan_recursos.state.time.time',return_value=1001):
                window.show()
                self.assertEqual(state.entry(demo.release)['presentation'],'postponed')
            window.controller.prepared.disconnect(window._confirm)
            prepared=[];completed=[]
            window.controller.prepared.connect(prepared.append)
            window.controller.completed.connect(lambda *result:completed.append(result))
            for scenario in ('cancelado','erro','novo'):
                demo.scenario=scenario
                prepared.clear();completed.clear()
                window.prepare()
                wait_until(lambda:bool(prepared))
                window.controller.confirm(prepared[0])
                wait_until(lambda:bool(completed))
                self.assertEqual(completed[0][0],scenario=='novo')
                self.assertEqual(state.entry(demo.release)['packages'],'installed' if scenario=='novo' else 'pending')
            previous=demo.release
            next_release=replace(previous,id='posterior',version='2.0',title='Uma novidade posterior',
                                 features=(replace(previous.features[0],packages=(replace(previous.packages[0],min_version='2.0'),)),))
            self.assertFalse(demo.plan(next_release).complete)
            demo.catalog=replace(demo.catalog,sequence=2,digest='e'*64,releases=(next_release,previous))
            window.close()
            window.reload()
            wait_until(lambda:window.worker is None)
            self.assertTrue(window.isVisible())
            self.assertEqual(window.current.key,next_release.key)
            self.assertEqual(state.entry(next_release)['packages'],'pending')
            self.assertEqual(state.entry(previous)['packages'],'installed')
            self.assertEqual(State(state.path).data['sequence'],2)
            window.close()

    def test_empty_catalog_clears_previous_details(self):
        window,demo,state=self.create()
        demo.catalog=replace(demo.catalog,sequence=2,digest='empty',releases=())
        window.reload();wait_until(lambda:window.worker is None)
        self.assertIsNone(window.current)
        self.assertIn('Nenhuma novidade publicada',window.summary.text())
        self.assertFalse(window.program_labels)
        self.assertFalse(window.know.isEnabled())

    def test_small_window_keeps_all_actions_inside_and_long_text_scrolls(self):
        window,demo,state=self.create()
        window.resize(640,480);window.show();APP.processEvents()
        self.assertFalse(window.history.isVisible())
        self.assertTrue(window.options.isVisible())
        self.assertIn(window.refresh,window.view.menu.actions())
        for button in (window.know,window.install,window.options,window.later):
            point=button.mapTo(window,button.rect().center())
            self.assertTrue(window.rect().contains(point))
        window.summary.setText('Descrição longa. '*300)
        window.status.setText('Erro detalhado. '*300)
        APP.processEvents()
        self.assertGreater(window.view.scroll.verticalScrollBar().maximum(),0)
        scroll_bottom=window.view.scroll.mapTo(window,window.view.scroll.rect().bottomLeft()).y()
        self.assertLess(scroll_bottom,window.know.mapTo(window,window.know.rect().topLeft()).y())
        self.assertTrue(window.install.font().bold())
        window.close()

    def test_apt_failure_preserves_authenticated_catalog_and_disables_install(self):
        window,demo,state=self.create()
        window.demo=None
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        window.directory=Path(directory.name)
        with patch('mainuan_recursos.gui.Config.load'), \
             patch('mainuan_recursos.gui.Repository.load',return_value=(demo.catalog,True)), \
             patch('mainuan_recursos.gui.system_identity',return_value={'distro_id':'mainuan'}), \
             patch('apt.Cache',side_effect=OSError('APT ocupado')):
            window.reload();wait_until(lambda:window.worker is None)
        self.assertIsNotNone(window.current)
        self.assertIn('APT ocupado',window.status.text())
        self.assertFalse(window.install.isEnabled())
        self.assertTrue(window.know.isEnabled())


class TrustRotationAuditTests(unittest.TestCase):
    def test_old_and_new_keys_then_revocation_keep_sequence_protection(self):
        import base64
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from mainuan_recursos.catalog import Config
        from helpers import NOW,HOSTS,catalog_dict
        keys={name:Ed25519PrivateKey.generate() for name in ('anterior','nova')}
        public={name:base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
                for name,key in keys.items()}
        config=Config('https://mainuan.example/catalog.json',HOSTS,public)
        raw=json.dumps(catalog_dict()).encode()
        def signature(name):
            return json.dumps({'key_id':name,'signature':base64.b64encode(keys[name].sign(raw)).decode()}).encode()
        state=State()
        for name in keys:
            state.accept(authenticate(raw,signature(name),config,NOW))
        revoked=replace(config,keys={'nova':public['nova']})
        with self.assertRaises(CatalogError):
            authenticate(raw,signature('anterior'),revoked,NOW)
        state.accept(authenticate(raw,signature('nova'),revoked,NOW))
        with self.assertRaises(CatalogError):
            state.accept(replace(catalog(),sequence=0))

    def test_url_spaces_are_not_normalized_differently_by_python_and_qt(self):
        for value in (' https://github.com/mainuan/repo','https://github.com/mainuan/repo ',
                      'https://github.com/mainuan/re po'):
            with self.assertRaises(CatalogError):
                scoped_url(value,('https://github.com/mainuan/',))
