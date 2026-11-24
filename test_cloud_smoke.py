"""Synthetic hosted-runner checks; no private project or model dependencies."""
import ast
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


class CloudSmoke(unittest.TestCase):
    def test_python_version(self):
        self.assertEqual(sys.version_info[:2], (3, 12))

    def test_utf8_path_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'Prüfung mit Leerzeichen'
            root.mkdir()
            target = root / 'Ergebnis.txt'
            staged = root / 'candidate.tmp'
            target.write_bytes(b'old')
            payload = 'Geprüft: 42'.encode('utf-8')
            staged.write_bytes(payload)
            os.replace(staged, target)
            self.assertEqual(target.read_bytes(), payload)
            self.assertFalse(staged.exists())

    def test_sqlite_transactions(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'test.sqlite3'
            with sqlite3.connect(db) as connection:
                connection.execute('CREATE TABLE result (id INTEGER PRIMARY KEY, value TEXT)')
                connection.execute('INSERT INTO result VALUES (?, ?)', (1, 'accepted'))
                connection.commit()
                connection.execute('UPDATE result SET value=?', ('rejected',))
                connection.rollback()
                self.assertEqual(connection.execute('SELECT value FROM result').fetchone(), ('accepted',))
            connection.close()

    def test_ast_and_digest(self):
        original = b'def calculate(x):\n    return x + 1\n'
        candidate = original.replace(b'+ 1', b'+ 2')
        self.assertNotEqual(hashlib.sha256(original).digest(), hashlib.sha256(candidate).digest())
        tree = ast.parse(candidate)
        self.assertEqual(tree.body[0].name, 'calculate')
        namespace = {}
        exec(compile(tree, '<synthetic>', 'exec'), namespace)
        self.assertEqual(namespace['calculate'](40), 42)

    def test_git_history_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / 'original'
            original.mkdir()
            def git(where, *args):
                return subprocess.check_output(['git', '-C', str(where), *args], text=True, timeout=30).strip()
            git(original, 'init', '-q')
            git(original, 'config', 'user.name', 'CI fixture')
            git(original, 'config', 'user.email', 'ci@example.invalid')
            git(original, 'config', 'core.autocrlf', 'false')
            source = original / 'sample.py'
            source.write_bytes(b'value = 1\n')
            git(original, 'add', 'sample.py')
            git(original, 'commit', '-qm', 'baseline')
            base = git(original, 'rev-parse', 'HEAD')
            candidate = root / 'candidate'
            git(root, 'clone', '-q', '--no-local', str(original), str(candidate))
            git(candidate, 'config', 'user.name', 'CI fixture')
            git(candidate, 'config', 'user.email', 'ci@example.invalid')
            (candidate / 'sample.py').write_bytes(b'value = 2\n')
            git(candidate, 'commit', '-qam', 'candidate')
            self.assertEqual(git(candidate, 'rev-parse', 'HEAD^'), base)
            self.assertEqual(git(original, 'rev-parse', 'HEAD'), base)
            self.assertEqual(source.read_bytes(), b'value = 1\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
