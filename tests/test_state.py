from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mainuan_recursos.catalog import CatalogError
from mainuan_recursos.state import State
from helpers import catalog, release


class StateTests(unittest.TestCase):
    def test_unseen_viewed_and_independent_installation(self):
        state, r = State(), release()
        self.assertTrue(state.due(r))
        state.viewed(r)
        self.assertFalse(state.due(r))
        self.assertEqual(state.entry(r)['packages'], 'unknown')

    def test_postponed_for_exactly_24_hours(self):
        state, r = State(), release()
        state.postpone(r, now=100)
        self.assertFalse(state.due(r, now=86499))
        self.assertTrue(state.due(r, now=86500))
        with patch('mainuan_recursos.state.time.time', return_value=200):
            state.viewed(r)
        self.assertEqual(state.entry(r)['presentation'], 'postponed')
        with patch('mainuan_recursos.state.time.time', return_value=86500):
            state.viewed(r)
        self.assertFalse(state.due(r, now=90000))

    def test_new_release_version_has_new_state(self):
        state, r = State(), release()
        state.viewed(r)
        self.assertTrue(state.due(replace(r, version='2.0')))

    def test_anti_rollback_and_equivocation(self):
        state, c = State(), catalog()
        state.accept(c)
        state.accept(c)
        for changed in (replace(c, sequence=0), replace(c, digest='changed')):
            with self.assertRaises(CatalogError):
                state.accept(changed)
        state.accept(replace(c, sequence=2, digest='new'))

    def test_atomic_persistence_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'state.json'
            state, r = State(path), release()
            state.accept(catalog())
            state.postpone(r, now=100)
            loaded = State(path)
            self.assertEqual(loaded.data, state.data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text('bad')
            with self.assertRaises(CatalogError):
                State(path)

    def test_observation_does_not_mark_viewed(self):
        from types import SimpleNamespace
        state, r = State(), release()
        state.observe(r, SimpleNamespace(complete=True))
        self.assertTrue(state.due(r))
        self.assertEqual(state.entry(r)['packages'], 'installed')
        state.observe(r, SimpleNamespace(complete=False))
        self.assertEqual(state.entry(r)['packages'], 'pending')
