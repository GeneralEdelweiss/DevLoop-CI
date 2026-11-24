import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ci_contracts import atomic_json, path_inventory, portable_path, strict_json, verify_blob


class PortablePaths(unittest.TestCase):
    def test_valid(self):
        for name in ('src/example.py', 'Prüfung mit Leerzeichen/Ä.txt', 'data/COM10.txt'):
            self.assertEqual(portable_path(name), name)

    def test_reject_invalid(self):
        for name in ('', '/root', '../x', 'a/../b', 'a//b', 'a/./b', 'a/',
                     'C:/a', 'C:a', 'a\\b', 'a:stream', 'a\x00b', 'a\nb',
                     'a./b', 'a /b', 'NUL.txt', 'aux', 'COM1.py', 'LPT².log',
                     'a/.GiT/config', 'a?b', 'a*b', 'a|b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                portable_path(name)

    def test_case_aliases(self):
        with self.assertRaises(ValueError):
            path_inventory(['src/A.py', 'SRC/a.py'])

    def test_file_directory_collisions_both_orders(self):
        for files in (['a', 'A/b'], ['A/b', 'a']):
            with self.assertRaises(ValueError):
                path_inventory(files)
        self.assertEqual(path_inventory(['a/b', 'a/c']), {'a/b', 'a/c'})


class StateContracts(unittest.TestCase):
    def test_json_utf8_and_nested(self):
        self.assertEqual(strict_json('{"label":"Ä","nested":{"ok":true}}'.encode()),
                         {'label': 'Ä', 'nested': {'ok': True}})

    def test_json_duplicates_and_nonfinite(self):
        for raw in ('{"x":1,"x":2}', '{"outer":{"x":1,"x":2}}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_atomic_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'Zustand.json'
            atomic_json(path, {'revision': 1})
            atomic_json(path, {'revision': 2, 'label': 'fertig ✓'})
            self.assertEqual(strict_json(path.read_bytes()), {'revision': 2, 'label': 'fertig ✓'})
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_replace_failure_preserves_old_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            atomic_json(path, {'revision': 1})
            before = path.read_bytes()
            with patch('ci_contracts.os.replace', side_effect=PermissionError('fixture')):
                with self.assertRaises(PermissionError):
                    atomic_json(path, {'revision': 2})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_invalid_json_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            atomic_json(path, {'revision': 1})
            before = path.read_bytes()
            for value in ({'invalid': float('nan')}, {1: 1, '1': 2}):
                with self.assertRaises((TypeError, ValueError)):
                    atomic_json(path, value)
                self.assertEqual(path.read_bytes(), before)

    def test_exact_digest_and_line_endings(self):
        raw = b'example\n'
        digest = hashlib.sha256(raw).hexdigest()
        verify_blob(raw, digest)
        for bad in (b'example\r\n', b'example', b'\xef\xbb\xbfexample\n'):
            with self.assertRaises(ValueError):
                verify_blob(bad, digest)
        with self.assertRaises(ValueError):
            verify_blob(raw, 'x' * 64)
